#!/usr/bin/env python3
"""Prepare an isolated, unsigned offline APK experiment; never builds/installs it."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

APK_SHA = 'af529b5fee62e944e571d3556b606ebcc860fa384bee3e0abd190ef342cf854f'
PINNED = {
'smali_classes3/rd.1/a.smali': '4ee88936620cf71990383213f3c48b5c04b512c5746cc1a5fd78a70f92b7f36a',
'AndroidManifest.xml': '8d2ec930a665e6e0603f0feac986f2f1a00cd783ee1cccf4b8de0454d49b9b30',
'smali/j9.1/a.smali': '570fb1b6b8a558a32ef02803ade7f84b50b3f3188c663d4e2e7dc502f5be9d54',
'smali_classes3/Ed/a.smali': '1015c8fade450cb867ab3a9ecf1fa88f0b9e56e5a720795b0fa3f1b985531e19',
'smali_classes3/odesk/johnlife/skylight/data/startup/WatchdogRepo.smali': 'd0c750f925730611c76be8e36c24978dc6e7ab5cf13abd4e1f64274397dc94b0',
'smali_classes3/odesk/johnlife/skylight/data/terminal/TerminalUtil.smali': '92bba0c38f7474f8faee9bed7ae69e013068c1e8ea568e93ada91e6cc18b2cd3',
'smali_classes3/odesk/johnlife/skylight/data/wifi/WifiConnectionStatusRepo.smali': '59cd77115e92c6fe71e2bb08bb4bf33089401a75608491012c02e314be30ae73',
}
OLD='com.skylight'
NEW='com.skylight.usbtest'
ANDROID='{http://schemas.android.com/apk/res/android}'
ET.register_namespace('android', 'http://schemas.android.com/apk/res/android')

def sha(data): return hashlib.sha256(data).hexdigest()
def require(ok, message):
    if not ok: raise SystemExit(message)

def inventory(root):
    result={}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(), f'Symlink not allowed: {p}')
        if p.is_file(): result[p.relative_to(root).as_posix()]=sha(p.read_bytes())
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True, type=Path)
    ap.add_argument('--source-apk', required=True, type=Path)
    ap.add_argument('--source-sha256', required=True)
    ap.add_argument('--output', required=True, type=Path)
    args=ap.parse_args()
    source=args.source.resolve(); output=args.output.resolve()
    require(args.source_sha256 == APK_SHA, 'Not the reviewed factory APK hash')
    require(sha(args.source_apk.read_bytes()) == APK_SHA, 'Source APK hash mismatch')
    require(source.is_dir(), 'Decoded source missing')
    require(not output.exists(), 'Output already exists; refusing overwrite')
    require(source != output and source not in output.parents and output not in source.parents,
            'Source/output must be separate trees')
    before=inventory(source)
    for name, expected in PINNED.items():
        require(before.get(name)==expected, f'Reviewed source changed: {name}')
    changes={}; operations=[]
    def load(name): return changes.get(name, (source/name).read_text())
    def save(name,text): changes[name]=text
    def stub(name, signature, body):
        text=load(name)
        pattern=re.compile(r'(?m)^(\.method [^\n]* '+re.escape(signature)+r'\n).*?^\.end method$', re.S)
        matches=list(pattern.finditer(text))
        require(len(matches)==1, f'Expected one method {name}: {signature}')
        save(name, pattern.sub(lambda m:m.group(1)+body+'\n.end method',text))
        operations.append({'file':name,'method':signature,'operation':'replace body'})
    void='    .locals 0\n    return-void'
    false='    .locals 1\n    const/4 v0, 0x0\n    return v0'
    unit='    .locals 1\n    sget-object v0, Lna/D;->a:Lna/D;\n    return-object v0'
    manifest='AndroidManifest.xml'
    root=ET.fromstring(load(manifest))
    require(root.get('package')==OLD, 'Unexpected package')
    require(root.attrib.pop(ANDROID+'sharedUserId')=='android.uid.system','Unexpected shared UID')
    require(root.attrib.pop('coreApp')=='true','Unexpected coreApp')
    root.set('package',NEW)
    protected=root.findall('protected-broadcast')
    require(len(protected)==1,'Unexpected protected broadcasts')
    for element in protected: root.remove(element)
    app=root.find('application'); require(app is not None,'Application missing')
    app.set(ANDROID+'label','Skylight USB Test')
    expected={'skylight.frame.data',OLD+'.androidx-startup',OLD+'.provider.datadog.rum',
              OLD+'.SentryInitProvider',OLD+'.SentryPerformanceProvider'}
    providers=app.findall('provider')
    require({p.get(ANDROID+'authorities') for p in providers}==expected,'Unexpected provider authorities')
    for p in providers:
        authority=p.get(ANDROID+'authorities')
        p.set(ANDROID+'authorities',NEW+'.frame.data' if authority=='skylight.frame.data' else authority.replace(OLD,NEW,1))
    permission=OLD+'.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'
    count=0
    for p in root:
        if p.tag in ('permission','uses-permission') and p.get(ANDROID+'name')==permission:
            p.set(ANDROID+'name',permission.replace(OLD,NEW,1)); count+=1
    require(count==2,'Expected own permission declaration and use')
    save(manifest,ET.tostring(root,encoding='unicode',xml_declaration=True)+'\n')
    operations.append({'file':manifest,'operation':'isolate manifest identity; preserve implementation names'})
    prefix='smali_classes3/odesk/johnlife/skylight/data/'
    wifi=prefix+'wifi/WifiConnectionStatusRepo.smali'
    old='invoke-virtual {p2, p1, p3}, Landroid/net/ConnectivityManager;->requestNetwork(Landroid/net/NetworkRequest;Landroid/net/ConnectivityManager$NetworkCallback;)V'
    new='invoke-virtual {p2, p3}, Landroid/net/ConnectivityManager;->registerDefaultNetworkCallback(Landroid/net/ConnectivityManager$NetworkCallback;)V'
    require(load(wifi).count(old)==1,'Network callback call mismatch')
    save(wifi,load(wifi).replace(old,new)); operations.append({'file':wifi,'operation':'observe real default network instead of requesting Wi-Fi transport'})
    activation='smali/j9.1/a.smali'
    stub(activation,'getHasCheckedForUpdatesDuringActivation()Z','    .locals 1\n    const/4 v0, 0x1\n    return v0')
    stub(activation,'statusReportAndInstallApks(Lra/d;)Ljava/lang/Object;',
         '    .locals 2\n    iget-object v0, p0, Lj9/a;->k:LOa/r0;\n'
         '    sget-object v1, Lcom/skylight/domain/features/activation/model/DownloadAndInstallProgress;->FINISHED:Lcom/skylight/domain/features/activation/model/DownloadAndInstallProgress;\n'
         '    invoke-virtual {v0, v1}, LOa/r0;->setValue(Ljava/lang/Object;)V\n'
         '    sget-object v0, Lna/D;->a:Lna/D;\n    return-object v0')
    repo=prefix+'startup/WatchdogRepo.smali'
    for sig in ['broadcastToWatchdog(Landroid/content/Intent;)V','broadcastToWatchdog$lambda$0(Lodesk/johnlife/skylight/data/startup/WatchdogRepo;Landroid/content/Intent;)V','reportStatus()V','uninstallWatchdog()V']:
        stub(repo,sig,void)
    stub(repo,'installWatchdog(ILra/d;)Ljava/lang/Object;',unit)
    manager='smali_classes3/Ed/a.smali'
    for sig in ['a()V','installWatchdogAndStartService(Ljava/lang/String;)V','startWatchdogService()V','uninstallWatchdog()V']:
        stub(manager,sig,void)
    stub(manager,'resetWatchdogService()Z',false)
    terminal=prefix+'terminal/TerminalUtil.smali'
    for sig in ['clearWifiFolder()V','expandLogs()V','rebootDevice()V','resetFrame()V','startWatchdogService()V','uninstallWatchdog()V']:
        stub(terminal,sig,void)
    for sig in ['installWatchdogAndStartService(Ljava/lang/String;)Z','resetWatchdogService()Z']:
        stub(terminal,sig,false)
    stub(terminal,'executeAsRoot([Ljava/lang/String;)Lodesk/johnlife/skylight/data/terminal/SuccessOrErrorOutput;',
         '    .locals 1\n    const/4 v0, 0x0\n    return-object v0')
    # Target string VALUES, never Java descriptors or class/package paths.
    literals={OLD:NEW,'skylight.frame.data':NEW+'.frame.data',permission:NEW+'.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION',
              ' pm clear com.skylight':' pm clear '+NEW,
              'pm clear com.skylight':'pm clear '+NEW}
    literal_counts={k:0 for k in literals}
    for name in before:
        if not name.endswith('.smali'): continue
        text=load(name)
        def replace(m):
            value=m.group(2)
            if value not in literals: return m.group(0)
            literal_counts[value]+=1
            return m.group(1)+literals[value]+m.group(3)
        updated=re.sub(r'(?m)^(\s*const-string(?:/jumbo)? [^,]+, ")([^"\n]*)(")$',replace,text)
        if updated!=text: save(name,updated)
    operations.append({'operation':'exact const-string identity substitutions only','counts':literal_counts})
    require(set(changes).issubset(PINNED), 'Unexpected unreviewed modified file')
    require(literal_counts[OLD] == 1, 'Unexpected self-package literal count')
    # No write occurs until all method and input guards have passed.
    require(inventory(source)==before,'Source changed while preparing')
    shutil.copytree(source,output)
    for name,text in changes.items(): (output/name).write_text(text)
    after=inventory(output)
    report={'source_apk_sha256':APK_SHA,'package':NEW,'label':'Skylight USB Test',
            'source_tree_digest':sha(json.dumps(before,sort_keys=True).encode()),
            'operations':operations,'changed_files':[
                {'path':n,'before':before[n],'after':after[n]} for n in sorted(after) if before[n]!=after[n]],
            'not_performed':['build','sign','install','device operations','backend requests'],
            'limitations':['Local experimental copy only; backend activation acceptance unknown.',
                'Telemetry and genuine activation remain enabled; no network calls were performed by this tool.',
                'No root privileges; privileged features can fail.',
                'APK rebuilding/signing and runtime verification still required.']}
    (output.parent/(output.name+'-patch-report.json')).write_text(json.dumps(report,indent=2)+'\n')
    require(inventory(source)==before,'Source unexpectedly changed')
    print(json.dumps({'package':NEW,'files_changed':len(report['changed_files']),
        'source_tree_digest':report['source_tree_digest'],'report':str(output.parent/(output.name+'-patch-report.json'))},indent=2))

if __name__=='__main__': main()
