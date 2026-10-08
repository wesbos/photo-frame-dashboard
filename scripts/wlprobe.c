/*
 * Read-only Broadcom bcmdhd radio probe. Issues only WLC "get" ioctls through
 * the driver's SIOCDEVPRIVATE entry point, like the wl utility. Requires root.
 *
 *   wlprobe [ifname] basic      noise, temperature, band, antenna settings
 *   wlprobe [ifname] counters   PHY/MAC receive counters (one line)
 *   wlprobe [ifname] rawcnt     hex dump of the counters iovar
 */
#include <errno.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#define SIOCDEVPRIVATE 0x89F0
#define WLC_GET_MAGIC 0
#define WLC_GET_VERSION 1
#define WLC_GET_TXANT 61
#define WLC_GET_ANTDIV 63
#define WLC_GET_BAND 140
#define WLC_GET_PHY_NOISE 135
#define WLC_GET_VAR 262
#define MAXLEN 8192

struct dhd_ioc {
	uint32_t cmd;
	void *buf;
	uint32_t len;
	uint8_t set;
	uint32_t used;
	uint32_t needed;
	uint32_t driver; /* not DHD magic, so dhd forwards to firmware */
};

static int sock;
static const char *ifname = "wlan0";
static uint8_t buf[MAXLEN];

static int wl_get(uint32_t cmd, void *data, uint32_t len)
{
	struct dhd_ioc ioc = { .cmd = cmd, .buf = data, .len = len };
	struct ifreq ifr;
	memset(&ifr, 0, sizeof(ifr));
	strncpy(ifr.ifr_name, ifname, IFNAMSIZ - 1);
	ifr.ifr_data = (void *)&ioc;
	return ioctl(sock, SIOCDEVPRIVATE, &ifr);
}

static int get_int(uint32_t cmd, int32_t *out)
{
	*out = 0;
	return wl_get(cmd, out, sizeof(*out));
}

static int get_var(const char *name, uint32_t len)
{
	memset(buf, 0, sizeof(buf));
	strncpy((char *)buf, name, sizeof(buf) - 1);
	return wl_get(WLC_GET_VAR, buf, len);
}

static void show_int(const char *label, uint32_t cmd)
{
	int32_t v;
	if (get_int(cmd, &v) < 0)
		printf("%s: error %s\n", label, strerror(errno));
	else
		printf("%s: %d (0x%x)\n", label, v, (uint32_t)v);
}

static void show_var_int(const char *name)
{
	if (get_var(name, 64) < 0)
		printf("%s: error %s\n", name, strerror(errno));
	else
		printf("%s: %d\n", name, *(int32_t *)buf);
}

static uint32_t u32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t u16(const uint8_t *p) { return p[0] | p[1] << 8; }

/* Offsets (in uint32 words) shared by wl_cnt_lt40mcst_v1_t and wl_cnt_ge40mcst_v1_t. */
static const struct { const char *name; int idx; } mcst[] = {
	{ "txallfrm", 0 }, { "rxanyerr", 20 }, { "rxbadfcs", 21 }, { "rxbadplcp", 22 },
	{ "rxcrsglitch", 23 }, { "rxstrt", 24 }, { "rxdtocast", 31 }, { "rxmgocast", 32 },
	{ "rxmgmcast", 37 }, { "rxbeaconmbss", 39 }, { "rxbeaconobss", 41 },
};

static void counters(int raw)
{
	if (get_var("counters", MAXLEN) < 0) {
		printf("counters: error %s\n", strerror(errno));
		return;
	}
	uint16_t version = u16(buf), datalen = u16(buf + 2);
	if (raw) {
		printf("version %u datalen %u\n", version, datalen);
		for (int i = 0; i < datalen + 4 && i < MAXLEN; i += 16) {
			printf("%04x:", i);
			for (int j = 0; j < 16; j += 4)
				printf(" %08x", u32(buf + i + j));
			printf("\n");
		}
		return;
	}
	if (version < 30) {
		printf("counters: legacy version %u, use rawcnt\n", version);
		return;
	}
	int found = 0;
	for (int off = 4; off + 4 <= 4 + datalen && off + 4 <= MAXLEN;) {
		uint16_t id = u16(buf + off), len = u16(buf + off + 2);
		const uint8_t *d = buf + off + 4;
		if (id == 0x200 || id == 0x300 || id == 0x400) {
			found = 1;
			printf("ucode(0x%x)", id);
			for (size_t i = 0; i < sizeof(mcst) / sizeof(mcst[0]); i++)
				if ((mcst[i].idx + 1) * 4 <= len)
					printf(" %s=%u", mcst[i].name, u32(d + mcst[i].idx * 4));
			printf("\n");
		}
		off += 4 + ((len + 3) & ~3);
	}
	if (!found)
		printf("counters: no ucode section found, use rawcnt\n");
}

int main(int argc, char **argv)
{
	const char *mode = "basic";
	if (argc > 2) {
		ifname = argv[1];
		mode = argv[2];
	} else if (argc > 1) {
		mode = argv[1];
	}
	sock = socket(AF_INET, SOCK_DGRAM, 0);
	if (sock < 0) {
		perror("socket");
		return 1;
	}
	if (!strcmp(mode, "counters"))
		counters(0);
	else if (!strcmp(mode, "rawcnt"))
		counters(1);
	else {
		show_int("magic", WLC_GET_MAGIC);
		show_int("ioctl_version", WLC_GET_VERSION);
		show_int("phy_noise_dbm", WLC_GET_PHY_NOISE);
		show_int("band", WLC_GET_BAND);
		show_int("antdiv", WLC_GET_ANTDIV);
		show_int("txant", WLC_GET_TXANT);
		show_var_int("phy_tempsense");
		show_var_int("rxchain");
		show_var_int("txchain");
		show_var_int("chanspec");
		if (get_var("ver", 256) == 0)
			printf("ver: %s", (char *)buf);
		if (get_var("phy_rssi_ant", 64) == 0)
			printf("phy_rssi_ant: ver=%u count=%u ant=[%d %d %d %d]\n", u16(buf), u16(buf + 2),
			       (int8_t)buf[4], (int8_t)buf[5], (int8_t)buf[6], (int8_t)buf[7]);
		else
			printf("phy_rssi_ant: error %s\n", strerror(errno));
	}
	close(sock);
	return 0;
}
