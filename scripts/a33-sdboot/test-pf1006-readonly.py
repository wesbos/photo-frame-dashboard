#!/usr/bin/env python3
"""Test the experimental U-Boot guards on the host. Do not access a device.

Usage: python3 scripts/a33-sdboot/test-pf1006-readonly.py /path/to/pinned/u-boot

Apply the patch to temporary copies of the pinned source. Compile the patched
block driver, EXT_CSD functions, and SPL sequence with fake MMC and PMIC calls.
Check that each PMIC error stops later operations and DRAM setup.
These tests check software guards. They do not test PF1006 hardware.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
PIN = "e50b1e8715011def8aff1588081a2649a2c6cd47"
DRIVER = "drivers/mmc/mmc_write.c"
FUNCTIONS = {
    "drivers/mmc/mmc.c": ("__mmc_switch", "mmc_switch", "mmc_boot_wp", "mmc_boot_wp_single_partition"),
    "board/sunxi/board.c": ("board_late_init", "pf1006_require_power_ok", "sunxi_board_init"),
}

SHIM = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <setjmp.h>
typedef unsigned long ulong;
typedef unsigned long lbaint_t;
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
#define CONFIG_IS_ENABLED(x) TEST_##x
#define IS_SD(m) ((m)->version & 0x80000000U)
#define UCLASS_MMC 1
#define LBAF "%lx"
#define MMC_RSP_R1 1
#define MMC_RSP_R1b 2
#define MMC_DATA_WRITE 1
#define SD_CMD_ERASE_WR_BLK_START 32
#define SD_CMD_ERASE_WR_BLK_END 33
#define MMC_CMD_ERASE_GROUP_START 35
#define MMC_CMD_ERASE_GROUP_END 36
#define MMC_CMD_ERASE 38
#define MMC_ERASE_ARG 0
#define MMC_TRIM_ARG 1
#define MMC_CMD_WRITE_SINGLE_BLOCK 24
#define MMC_CMD_WRITE_MULTIPLE_BLOCK 25
#define MMC_CMD_STOP_TRANSMISSION 12
#define MMC_CMD_SWITCH 6
#define MMC_SWITCH_MODE_WRITE_BYTE 3
#define DEFAULT_CMD6_TIMEOUT_MS 500
#define EXT_CSD_CMD_SET_NORMAL 1
#define EXT_CSD_ERASE_GROUP_DEF 175
#define EXT_CSD_PART_CONF 179
#define EXT_CSD_BUS_WIDTH 183
#define EXT_CSD_HS_TIMING 185
#define EXT_CSD_BOOT_WP 173
#define EXT_CSD_BOOT_WP_B_PWR_WP_EN 1
#define EXT_CSD_BOOT_WP_B_SEC_WP_SEL 128
#define EXT_CSD_BOOT_WP_B_PWR_WP_SEC_SEL 2
#define MMC_STATUS_SWITCH_ERROR 128
#define MMC_STATUS_RDY_FOR_DATA 256
#define MMC_STATUS_CURR_STATE 0x1e00
#define MMC_STATE_TRANS 0x800
#define pr_debug(...) ((void)0)
struct blk_desc { int devnum, hwpart; ulong lba; };
struct udevice { struct blk_desc desc; };
struct mmc_config { ulong b_max; };
struct mmc {
    unsigned version, high_capacity, write_bl_len, erase_grp_size;
    unsigned can_trim, gen_cmd6_time, part_switch_time, part_config;
    struct { ulong au; } ssr;
    struct mmc_config *cfg;
    struct blk_desc desc;
};
struct mmc_cmd { unsigned cmdidx, cmdarg, resp_type; };
struct mmc_data { const void *src; ulong blocks, blocksize, flags; };
static struct mmc cards[2];
static unsigned selections, blocklens, transfers, writes, erases, switches;
static void reset_counts(void) {
    selections = blocklens = transfers = writes = erases = switches = 0;
}
static void *dev_get_uclass_plat(struct udevice *dev) { return &dev->desc; }
static struct mmc *find_mmc_device(int dev) { return &cards[dev]; }
static int blk_select_hwpart_devnum(int cls, int dev, int part) {
    selections++; return 0;
}
static unsigned div_u64_rem(u64 n, unsigned divisor, u32 *rem) {
    *rem = n % divisor; return n / divisor;
}
static struct blk_desc *mmc_get_blk_desc(struct mmc *mmc) { return &mmc->desc; }
static int mmc_set_blocklen(struct mmc *mmc, unsigned size) { blocklens++; return 0; }
static int mmc_send_cmd(struct mmc *mmc, struct mmc_cmd *cmd, struct mmc_data *data) {
    transfers++;
    if (data && (data->flags & MMC_DATA_WRITE)) writes += data->blocks;
    if (cmd->cmdidx == MMC_CMD_ERASE) erases++;
    if (cmd->cmdidx == MMC_CMD_SWITCH) switches++;
    return 0;
}
static int mmc_poll_for_busy(struct mmc *mmc, int ms) { return 0; }
static bool mmc_host_is_spi(struct mmc *mmc) { return false; }
static int mmc_send_cmd_retry(struct mmc *mmc, struct mmc_cmd *cmd,
                              struct mmc_data *data, unsigned retries) {
    return mmc_send_cmd(mmc, cmd, data);
}
static ulong get_timer(ulong base) { return 0; }
static int mmc_wait_dat0(struct mmc *mmc, int state, int us) { return 0; }
static void mdelay(int ms) {}
static void udelay(int us) {}
static int mmc_send_status(struct mmc *mmc, unsigned *status) {
    *status = MMC_STATUS_RDY_FOR_DATA | MMC_STATE_TRANS; return 0;
}
struct global_data { ulong ram_size; };
static struct global_data board_data;
static struct global_data *gd = &board_data;
static ulong exported_ram_bytes;
static int env_set_hex(const char *key, ulong value) {
    assert(strcmp(key, "pf1006_ram_bytes") == 0);
    exported_ram_bytes = value; return 0;
}
#define SZ_256M (256UL << 20)
static ulong detected_ram, stored_ram;
static unsigned clock_changes, dram_calls;
static jmp_buf hang_jump;
static ulong sunxi_dram_init(void) { dram_calls++; return detected_ram; }
static void hang(void) { longjmp(hang_jump, 1); }
static void sunxi_spl_store_dram_size(ulong size) { stored_ram = size; }
static unsigned get_board_sys_clk(void) { return 1008000000; }
static void clock_set_pll1(unsigned frequency) { clock_changes++; }
#define CONFIG_AXP221_POWER 1
#define CONFIG_AXP_DISABLE_BOOT_ON_POWERON 0
#define IS_ENABLED(x) (x)
#define BIT(x) (1U << (x))
#define AXP_POWER_STATUS 0
#define AXP_POWER_STATUS_ALDO_IN BIT(0)
#define CONFIG_AXP_DCDC1_VOLT 3000
#define CONFIG_AXP_DCDC2_VOLT 1100
#define CONFIG_AXP_DCDC3_VOLT 1200
#define CONFIG_AXP_DCDC4_VOLT 0
#define CONFIG_AXP_DCDC5_VOLT 1500
#define CONFIG_AXP_ALDO1_VOLT 3000
#define CONFIG_AXP_ALDO2_VOLT 2500
#define CONFIG_AXP_ALDO3_VOLT 3000
#define CONFIG_AXP_DLDO1_VOLT 0
#define CONFIG_AXP_DLDO2_VOLT 0
#define CONFIG_AXP_DLDO3_VOLT 0
#define CONFIG_AXP_DLDO4_VOLT 0
#define CONFIG_AXP_ELDO1_VOLT 0
#define CONFIG_AXP_ELDO2_VOLT 0
#define CONFIG_AXP_ELDO3_VOLT 0
static int fail_power_step = -1;
static unsigned power_calls;
static int fake_power(unsigned step, unsigned value) {
    const unsigned expected[] = {0, 3000, 1100, 1200, 0, 1500, 3000, 2500,
                                 3000, 0, 0, 0, 0, 0, 0, 0};
    assert(step == power_calls && value == expected[step]);
    power_calls++;
    return (int)step == fail_power_step ? -EIO : 0;
}
static int axp_init(void) { return fake_power(0, 0); }
static int axp_set_dcdc1(unsigned v) { return fake_power(1, v); }
static int axp_set_dcdc2(unsigned v) { return fake_power(2, v); }
static int axp_set_dcdc3(unsigned v) { return fake_power(3, v); }
static int axp_set_dcdc4(unsigned v) { return fake_power(4, v); }
static int axp_set_dcdc5(unsigned v) { return fake_power(5, v); }
static int axp_set_aldo1(unsigned v) { return fake_power(6, v); }
static int axp_set_aldo2(unsigned v) { return fake_power(7, v); }
static int axp_set_aldo3(unsigned v) { return fake_power(8, v); }
static int axp_set_dldo(unsigned number, unsigned v) { return fake_power(8 + number, v); }
static int axp_set_eldo(unsigned number, unsigned v) { return fake_power(12 + number, v); }
static int pmic_bus_read(unsigned reg, u8 *value) { assert(0); return -EIO; }
static int pmic_bus_write(unsigned reg, u8 value) { assert(0); return -EIO; }
"""

MAIN = r"""
int main(void) {
    struct mmc_config cfg = {.b_max = 8};
    char data[1024] = {0};
    const unsigned sizes[] = {0, 64, 128, 255, 256, 512, 1024};
    for (unsigned i = 0; i < sizeof(sizes) / sizeof(sizes[0]); i++) {
        detected_ram = (ulong)sizes[i] << 20;
        stored_ram = 0;
        clock_changes = 0;
        power_calls = dram_calls = 0;
        if (!setjmp(hang_jump)) {
            sunxi_board_init();
            assert(detected_ram >= SZ_256M);
            assert(stored_ram == detected_ram && clock_changes == 1);
        } else {
            assert(detected_ram < SZ_256M);
            assert(stored_ram == 0 && clock_changes == 0);
        }
        assert(power_calls == 16 && dram_calls == 1);
    }
    /* Stop after each PMIC error, before another regulator call or DRAM setup. */
    for (int step = 0; step < 16; step++) {
        detected_ram = 1024UL << 20;
        stored_ram = 0;
        power_calls = dram_calls = clock_changes = 0;
        fail_power_step = step;
        if (!setjmp(hang_jump)) {
            sunxi_board_init();
            assert(!"PMIC error did not stop the loader");
        }
        assert(power_calls == (unsigned)step + 1);
        assert(dram_calls == 0 && stored_ram == 0 && clock_changes == 0);
    }
    fail_power_step = -1;
    for (unsigned bits = 26; bits < 31; bits++) {
        gd->ram_size = 1UL << bits;
        assert(board_late_init() == 0);
        assert(exported_ram_bytes == gd->ram_size);
    }
    for (int dev = 0; dev < 2; dev++) {
        struct mmc *card = &cards[dev];
        struct blk_desc desc = {.devnum = dev, .hwpart = 0, .lba = 4096};
        card->cfg = &cfg;
        card->desc = desc;
        card->high_capacity = 1;
        card->write_bl_len = 512;
        card->erase_grp_size = 1;
#if TEST_BLK
        struct udevice device = {.desc = desc};
        struct udevice *target = &device;
#else
        struct blk_desc *target = &desc;
#endif
        /* Refuse eMMC and unknown cards at either device index. */
        for (unsigned version = 0; version < 2; version++) {
            card->version = version;
            for (int part = 0; part < 8; part++) {
#if TEST_BLK
                device.desc.hwpart = part;
#else
                desc.hwpart = part;
#endif
                reset_counts();
                assert(mmc_bwrite(target, 8, 2, data) == 0);
                assert(mmc_berase(target, 8, 2) == 0);
                assert(selections == 0 && blocklens == 0 && transfers == 0);
            }
        }
        /* SD uses partition 0. Check both single-block and multi-block writes. */
#if TEST_BLK
        device.desc.hwpart = 0;
#else
        desc.hwpart = 0;
#endif
        card->version = 0x80000000U;
        reset_counts();
        assert(mmc_bwrite(target, 8, 1, data) == 1);
        assert(mmc_bwrite(target, 8, 2, data) == 2);
        assert(writes == 3 && selections == 2);
        assert(mmc_berase(target, 8, 2) == 2);
        assert(erases > 0);
        /* Permit the volatile settings used during MMC initialization. */
        card->version = 1;
        for (int index = 0; index < 256; index++) {
            reset_counts();
            int result = mmc_switch(card, EXT_CSD_CMD_SET_NORMAL, index, 1);
            bool allowed = index == EXT_CSD_BUS_WIDTH ||
                           index == EXT_CSD_HS_TIMING ||
                           index == EXT_CSD_ERASE_GROUP_DEF ||
                           index == EXT_CSD_PART_CONF;
            assert(result == (allowed ? 0 : -EPERM));
            assert(switches == (allowed ? 1U : 0U));
        }
        /* Change only PARTITION_ACCESS. Keep the boot-selection bits. */
        card->part_config = 0x48;
        for (unsigned value = 0; value < 256; value++) {
            reset_counts();
            int result = mmc_switch(card, EXT_CSD_CMD_SET_NORMAL,
                                    EXT_CSD_PART_CONF, value);
            bool allowed = (value & ~7U) == 0x48U;
            assert(result == (allowed ? 0 : -EPERM));
            assert(switches == (allowed ? 1U : 0U));
        }
        /* Only the normal command set may use the allowed settings. */
        for (unsigned set = 0; set < 256; set++) {
            reset_counts();
            int result = mmc_switch(card, set, EXT_CSD_BUS_WIDTH, 1);
            bool allowed = set == EXT_CSD_CMD_SET_NORMAL;
            assert(result == (allowed ? 0 : -EPERM));
            assert(switches == (allowed ? 1U : 0U));
        }
        reset_counts();
        assert(mmc_switch(card, 1, EXT_CSD_ERASE_GROUP_DEF, 2) == -EPERM);
        assert(mmc_boot_wp(card) == -EPERM);
        for (int part = -1; part < 3; part++)
            assert(mmc_boot_wp_single_partition(card, part) == -EPERM);
        assert(switches == 0 && transfers == 0);
    }
    puts("PASS: block write/erase, EXT_CSD, boot protection, RAM, and PMIC guards; SD writes work");
    return 0;
}
"""


def function(source, name):
    """Copy a complete C function without changing its code."""
    match = re.search(r"^(?:static )?(?:int|void) " + re.escape(name) + r"\([^;]+?\n\{", source, re.M)
    if not match:
        raise RuntimeError(f"C function is missing: {name}")
    depth = 1
    end = match.end()
    while depth:
        if end >= len(source):
            raise RuntimeError(f"C function has no closing brace: {name}")
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end] + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise SystemExit(f"STOP: Expected U-Boot {PIN}. Found {head}.")
    cc = os.environ.get("CC", "cc")
    if not shutil.which(cc):
        raise SystemExit(f"STOP: C compiler is not available: {cc}")
    with tempfile.TemporaryDirectory(prefix="pf1006-mmc-test-") as folder:
        temp = Path(folder)
        for name in (DRIVER, *FUNCTIONS):
            destination = temp / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Read the pinned commit. Ignore changes in the source checkout.
            destination.write_bytes(subprocess.check_output(
                ["git", "-C", str(source), "show", f"{PIN}:{name}"]))
        subprocess.run(["git", "apply", str(HERE / "pf1006-readonly.patch")], cwd=temp, check=True)
        parts = [SHIM, re.sub(r"^#include .*\n", "", (temp / DRIVER).read_text(), flags=re.M)]
        for name, functions in FUNCTIONS.items():
            source_text = (temp / name).read_text()
            parts.extend(function(source_text, function_name) for function_name in functions)
        test = temp / "test.c"
        test.write_text("".join(parts) + MAIN)
        for block_api in (0, 1):
            binary = temp / f"test-{block_api}"
            subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-parameter", "-Wno-unused-function",
                            "-Wno-sign-compare", f"-DTEST_BLK={block_api}",
                            str(test), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            print(f"BLK={block_api}: {result.stdout.strip().splitlines()[-1]}")


if __name__ == "__main__":
    main()
