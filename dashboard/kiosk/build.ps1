# Windows equivalent of build.sh. Builds kiosk\build\homehq.apk without Gradle.
# Needs a JDK 17 and Android build-tools 34 + platform 34 (see build.sh for the sdkmanager line).
#   .\build.ps1
# If Windows blocks the unsigned script, run it once with:
#   powershell -ExecutionPolicy Bypass -File .\build.ps1
# Install on the tablet: adb install -r build\homehq.apk
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$bt  = "$sdk\build-tools\34.0.0"
$jar = "$sdk\platforms\android-34\android.jar"
$ks  = "$env:USERPROFILE\.android\debug.keystore"
if (-not (Test-Path $jar)) { throw "android.jar not found at $jar" }

if (Test-Path build) { Remove-Item build -Recurse -Force }
New-Item -ItemType Directory build\gen, build\classes | Out-Null

function Run($exe, [string[]]$a) {
  & $exe @a
  if ($LASTEXITCODE -ne 0) { throw "$exe failed ($LASTEXITCODE)" }
}

Run "$bt\aapt2.exe" @('compile', '--dir', 'res', '-o', 'build\res.zip')
# Target 28: see build.sh.
Run "$bt\aapt2.exe" @('link', '-o', 'build\base.apk', '-I', $jar, '--manifest', 'AndroidManifest.xml', 'build\res.zip',
  '--java', 'build\gen', '--min-sdk-version', '23', '--target-sdk-version', '28', '--version-code', '2', '--version-name', '1.1')

$src = @(Get-ChildItem src -Recurse -Filter *.java | % FullName) + @('build\gen\com\wesbos\homehq\R.java')
Run 'javac' (@('-nowarn', '-source', '8', '-target', '8', '-classpath', $jar, '-d', 'build\classes') + $src)

$classes = Get-ChildItem build\classes -Recurse -Filter *.class | % FullName
Run "$bt\d8.bat" (@('--min-api', '23', '--lib', $jar, '--output', 'build') + $classes)

# Add classes.dex to the APK (it is a zip).
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::Open((Resolve-Path build\base.apk), 'Update')
[IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Resolve-Path build\classes.dex), 'classes.dex') | Out-Null
$zip.Dispose()

Run "$bt\zipalign.exe" @('-f', '4', 'build\base.apk', 'build\aligned.apk')

if (-not (Test-Path $ks)) {
  New-Item -ItemType Directory -Force (Split-Path $ks) | Out-Null
  Run 'keytool' @('-genkeypair', '-keystore', $ks, '-storepass', 'android', '-keypass', 'android', '-alias', 'androiddebugkey',
    '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000', '-dname', 'CN=Android Debug,O=Android,C=US')
}
Run "$bt\apksigner.bat" @('sign', '--ks', $ks, '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', 'build\homehq.apk', 'build\aligned.apk')
Write-Output "Built kiosk\build\homehq.apk"
