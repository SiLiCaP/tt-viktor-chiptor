"""Instruction-level profile of ML-KEM-512 (PQClean clean, compiled for the Cortex-M33) under emulation.

    make -C tools/mlkem_profile run            # or: python profile.py mlkem.elf [--json out.json]

Every executed instruction is counted against the function it belongs to (inlining is off in the build,
so the function names are the algorithm's steps), per phase: keygen, encaps, decaps. Functions are then
grouped into the parts of the ML-KEM chain (CATEGORIES). Instruction counts are not cycles: the M33 runs
most of this code at about 1-1.5 cycles per instruction, so the shares are what to read, not the totals.
"""
import bisect
import json
import sys

from elftools.elf.elffile import ELFFile
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_INTR, UC_MODE_MCLASS, UC_MODE_THUMB, Uc
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP

# function name (without the PQCLEAN_MLKEM512_CLEAN_ prefix) -> part of the ML-KEM chain
CATEGORIES = [
    ("SHA-3 / SHAKE (Keccak)", ("KeccakF1600", "keccak_", "shake", "sha3_", "load64", "store64",
                                "kyber_shake", "hash_", "prf", "rkprf", "xof", "theta", "keccak")),
    ("NTT, inverse NTT, basemul", ("ntt", "invntt", "fqmul", "basemul", "montgomery_reduce", "tomont",
                                   "polyvec_basemul")),
    ("rejection sampling (SampleNTT)", ("rej_uniform", "gen_matrix")),
    ("CBD sampling (SamplePolyCBD)", ("cbd", "load24", "load32", "getnoise")),
    ("compress / decompress", ("compress", "decompress")),
    ("encode / decode (ByteEncode12, msg)", ("tobytes", "frombytes", "tomsg", "frommsg", "pack_", "unpack_")),
    ("polynomial add / sub / reduce", ("poly_add", "poly_sub", "polyvec_add", "reduce", "csubq")),
    ("FO compare + select (verify, cmov)", ("verify", "cmov")),
    ("memcpy / memset", ("memcpy", "memset", "memmove")),
]


def category(fn):
    f = fn.replace("PQCLEAN_MLKEM512_CLEAN_", "").replace("PQCLEAN_", "")
    for cat, keys in CATEGORIES:
        if any(k in f for k in keys):
            return cat
    return "other (KEM glue)"


def load(path):
    elf = ELFFile(open(path, "rb"))
    segs = [(s["p_vaddr"], s.data()) for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
    funcs = sorted((s["st_value"] & ~1, s["st_value"] + max(s["st_size"], 2), s.name)
                   for s in elf.get_section_by_name(".symtab").iter_symbols()
                   if s["st_info"]["type"] == "STT_FUNC" and s.name)
    syms = {s.name: s["st_value"] for s in elf.get_section_by_name(".symtab").iter_symbols()}
    return segs, funcs, syms


def main():
    path = sys.argv[1]
    segs, funcs, syms = load(path)
    starts = [f[0] for f in funcs]
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.mem_map(0x00000000, 1 << 20)
    uc.mem_map(0x20000000, 512 << 10)
    for addr, data in segs:
        uc.mem_write(addr, data)
    uc.reg_write(UC_ARM_REG_SP, 0x20000000 + (512 << 10) - 16)
    phase_addr = syms["phase"] & ~1
    counts = {}
    state = {"phase": "start", "fn_cache": (0, 0, "?")}
    names = {1: "keygen", 2: "encaps", 3: "decaps"}

    def on_code(uc_, addr, size, _):
        lo, hi, name = state["fn_cache"]
        if not lo <= addr < hi:
            i = bisect.bisect_right(starts, addr) - 1
            lo, hi, name = funcs[i] if i >= 0 else (0, 0, "?")
            state["fn_cache"] = (lo, hi, name)
        if addr == phase_addr:
            r0 = uc_.reg_read(UC_ARM_REG_R0)
            state["phase"] = names.get(r0, f"end:{r0:#x}")
        key = (state["phase"], name)
        counts[key] = counts.get(key, 0) + 1

    def on_intr(uc_, intno, _):
        uc_.emu_stop()

    uc.hook_add(UC_HOOK_CODE, on_code)
    uc.hook_add(UC_HOOK_INTR, on_intr)
    uc.emu_start(syms["run"] | 1, 0xFFFFFFFF, count=200_000_000)
    end = state["phase"]
    if end != "end:0xc0de":
        raise SystemExit(f"run did not finish with matching keys: {end}")

    ops = ("keygen", "encaps", "decaps")
    cats = [c for c, _ in CATEGORIES] + ["other (KEM glue)"]
    table = {op: {c: 0 for c in cats} for op in ops}
    fn_tot = {}
    for (ph, fn), n in counts.items():
        if ph in table:
            table[ph][category(fn)] += n
            fn_tot[fn] = fn_tot.get(fn, 0) + n
    tot = {op: sum(table[op].values()) for op in ops}
    print(f"ML-KEM-512 (PQClean clean, Cortex-M33 -O2 -fno-inline), instructions executed; keys match\n")
    print(f"{'part of the chain':40}" + "".join(f"{op:>16}" for op in ops) + f"{'exchange':>16}")
    for c in cats:
        ex = sum(table[op][c] for op in ops)
        print(f"{c:40}" + "".join(f"{table[op][c]:>9,} {100 * table[op][c] / tot[op]:4.1f}%" for op in ops)
              + f"{ex:>9,} {100 * ex / sum(tot.values()):4.1f}%")
    print(f"{'total':40}" + "".join(f"{tot[op]:>15,} " for op in ops) + f"{sum(tot.values()):>15,}")
    print("\nlargest functions (whole exchange):")
    for fn, n in sorted(fn_tot.items(), key=lambda kv: -kv[1])[:18]:
        print(f"  {fn.replace('PQCLEAN_MLKEM512_CLEAN_', ''):42} {n:>11,}  {100 * n / sum(tot.values()):5.1f}%  [{category(fn)}]")
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump({"table": table, "total": tot, "functions": fn_tot}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
