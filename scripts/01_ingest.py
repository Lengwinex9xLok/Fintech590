"""Gate 1: ingest every CDR Call Report bulk ZIP into a bank x quarter Parquet panel,
and reconcile row counts by form type (031 / 041 / 051) to the CDR panel of reporters.

Usage:  python scripts/01_ingest.py
Input:  data/cdr_bulk/FFIEC CDR Call Bulk All Schedules MMDDYYYY.zip  (one per quarter)
Output: data/phase3/panel_raw.parquet       bank x quarter, coalesced raw fields
        data/phase3/dim_bank.parquet        latest name / state / form type per RSSD
        data/phase3/reconciliation.csv      row counts by form type, every quarter
"""
import io
import re
import sys
import zipfile
from datetime import date

import pandas as pd

from config import BULK_DIR, OUT_DIR, RAW_FIELDS

NEEDED = {code for _, codes, _ in RAW_FIELDS.values() for code in codes}


def quarter_from_name(name: str) -> date:
    m = re.search(r"(\d{2})(\d{2})(\d{4})", name)
    if not m:
        raise ValueError(f"no MMDDYYYY date in {name}")
    mm, dd, yyyy = map(int, m.groups())
    return date(yyyy, mm, dd)


class Source:
    """A quarter's bulk data: either the CDR ZIP or the folder it unzips to."""
    def __init__(self, path):
        self.path = path
        self.zf = zipfile.ZipFile(path) if path.suffix.lower() == ".zip" else None

    def namelist(self):
        if self.zf:
            return self.zf.namelist()
        return [p.name for p in self.path.iterdir()]

    def read(self, member):
        return self.zf.read(member) if self.zf else (self.path / member).read_bytes()

    def open(self, member):
        return self.zf.open(member) if self.zf else open(self.path / member, "rb")


def read_txt(zf, member: str, usecols=None) -> pd.DataFrame:
    raw = zf.read(member).decode("latin-1")
    df = pd.read_csv(io.StringIO(raw), sep="\t", dtype=str, quotechar='"',
                     usecols=usecols, low_memory=False)
    df.columns = [c.strip().strip('"') for c in df.columns]
    return df


def header(zf, member):
    first = zf.open(member).readline().decode("latin-1")
    return [c.strip().strip('"') for c in first.rstrip("\r\n").split("\t")]


def ingest_zip(path):
    q = quarter_from_name(path.name)
    zf = Source(path)
    if True:
        members = [m for m in zf.namelist() if m.lower().endswith(".txt")]
        por_m = [m for m in members if " POR " in m]
        if not por_m:
            raise ValueError(f"{path.name}: no POR (panel of reporters) file")
        por = read_txt(zf, por_m[0])
        por = por.rename(columns={
            "Financial Institution Name": "name",
            "Financial Institution State": "state",
            "Financial Institution City": "city",
            "Financial Institution Filing Type": "form_type",
            "FDIC Certificate Number": "fdic_cert",
        })
        por["IDRSSD"] = por["IDRSSD"].str.strip()
        por["form_type"] = por["form_type"].str.strip().str.zfill(3)   # 31 -> 031

        # Pull only the MDRM columns we need, from whichever schedule file has them.
        parts, rc_filers = [], None
        for m in members:
            if m in por_m:
                continue
            cols = header(zf, m)
            want = [c for c in cols if c in NEEDED]
            if "Schedule RC " in m and "RC" == m.split("Schedule ")[-1].split(" ")[0]:
                rc_filers = set(read_txt(zf, m, usecols=["IDRSSD"]).iloc[1:]["IDRSSD"].str.strip())
            if not want:
                continue
            df = read_txt(zf, m, usecols=["IDRSSD"] + want)
            df = df.iloc[1:]                                  # row 2 is the MDRM description row: drop it
            df["IDRSSD"] = df["IDRSSD"].str.strip()
            parts.append(df.set_index("IDRSSD"))

    wide = pd.concat(parts, axis=1)
    wide = wide.loc[:, ~wide.columns.duplicated()]
    # Ratios come as "9.5831%"; strip % and thousands separators before casting
    wide = wide.apply(lambda c: pd.to_numeric(c.str.replace("%", "", regex=False)
                                              .str.replace(",", "", regex=False).str.strip(), errors="coerce"))

    # Coalesce RCFD -> RCON (consolidated first). Keep which code supplied the value (lineage).
    out = pd.DataFrame(index=wide.index)
    for key, (_, codes, _) in RAW_FIELDS.items():
        present = [c for c in codes if c in wide.columns]
        val = pd.Series(float("nan"), index=wide.index)
        for c in present:
            val = val.fillna(wide[c])
        out[key] = val

    out = out.reset_index().rename(columns={"IDRSSD": "rssd_id"})
    out = out.merge(por[["IDRSSD", "form_type"]].rename(columns={"IDRSSD": "rssd_id"}),
                    on="rssd_id", how="left")
    out.insert(1, "quarter", pd.Timestamp(q))

    # Reconciliation for this quarter
    por_counts = por.groupby("form_type").size().rename("cdr_filers")
    panel_counts = out.groupby("form_type").size().rename("panel_rows")
    rec = pd.concat([por_counts, panel_counts], axis=1).fillna(0).astype(int)
    rec.loc["TOTAL"] = rec.sum()
    rec["diff"] = rec["panel_rows"] - rec["cdr_filers"]
    rec.insert(0, "quarter", q.isoformat())
    missing = set(por["IDRSSD"]) - set(out["rssd_id"])
    extra = set(out["rssd_id"]) - set(por["IDRSSD"])
    rec["rssd_in_por_not_panel"] = len(missing)
    rec["rssd_in_panel_not_por"] = len(extra)
    if rc_filers is not None:
        rec["rc_schedule_rows"] = len(rc_filers)

    dim = por[["IDRSSD", "name", "city", "state", "form_type", "fdic_cert"]].rename(columns={"IDRSSD": "rssd_id"})
    dim["quarter"] = pd.Timestamp(q)
    return out, rec.reset_index().rename(columns={"index": "form_type"}), dim


def main():
    # Accept the ZIPs as downloaded, or the folders they unzip to (skip a folder if its ZIP is also there)
    found = {}
    for p in BULK_DIR.iterdir():
        if p.suffix.lower() == ".zip" or (p.is_dir() and "Call Bulk" in p.name):
            q = quarter_from_name(p.name)
            if q not in found or p.is_dir():
                found[q] = p
    zips = [found[q] for q in sorted(found)]
    if not zips:
        sys.exit(f"No ZIPs in {BULK_DIR}. Download 'Call Reports -- Single Period' (tab delimited) from CDR.")
    panels, recs, dims = [], [], []
    for z in zips:
        p, r, d = ingest_zip(z)
        print(f"{z.name}: {len(p):,} banks")
        panels.append(p); recs.append(r); dims.append(d)

    panel = pd.concat(panels, ignore_index=True)
    panel["rssd_id"] = panel["rssd_id"].astype("int64")
    panel.to_parquet(OUT_DIR / "panel_raw.parquet", index=False)

    dim = pd.concat(dims).sort_values("quarter").groupby("rssd_id").last().reset_index()
    dim["rssd_id"] = dim["rssd_id"].astype("int64")
    dim.to_parquet(OUT_DIR / "dim_bank.parquet", index=False)

    rec = pd.concat(recs, ignore_index=True)
    rec.to_csv(OUT_DIR / "reconciliation.csv", index=False)

    latest = rec[rec["quarter"] == rec["quarter"].max()]
    print("\nGate 1 reconciliation, latest quarter:")
    print(latest.to_string(index=False))
    ok = (latest["diff"] == 0).all() and (latest["rssd_in_por_not_panel"] == 0).all()
    print("\nRECONCILES" if ok else "\nDOES NOT RECONCILE: check the rows above")
    print(f"\nPanel: {len(panel):,} bank-quarters, {panel['rssd_id'].nunique():,} banks, "
          f"{panel['quarter'].nunique()} quarters -> {OUT_DIR / 'panel_raw.parquet'}")


if __name__ == "__main__":
    main()
