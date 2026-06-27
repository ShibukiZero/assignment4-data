from __future__ import annotations

import argparse
import gzip
import re
from pathlib import Path


DEFAULT_INPUT_PATH = Path("data/raw/wikipedia/enwiki-latest-externallinks.sql.gz")
DEFAULT_OUTPUT_PATH = Path("data/raw/wikipedia/extracted_urls.txt.gz")

INSERT_PREFIX = "INSERT INTO `externallinks` VALUES "
URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract external URLs from a Wikimedia externallinks SQL dump and write "
            "them as one URL per line to a gzipped text file."
        )
    )
    parser.add_argument(
        "--input-path",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to enwiki externallinks SQL dump (.sql or .sql.gz).",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to gzipped output text file (one URL per line).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1_000_000,
        help="Print a progress update every N extracted URLs.",
    )
    return parser.parse_args()


def open_text_for_read(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("rt", encoding="utf-8", errors="replace")


def open_text_for_write(path: Path):
    if path.suffix != ".gz":
        raise ValueError("Output path should end with .gz so it matches the assignment-style artifact.")
    path.parent.mkdir(parents=True, exist_ok=True)
    return gzip.open(path, "wt", encoding="utf-8")


def mysql_unescape(value: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        i += 1
        if i >= len(value):
            out.append("\\")
            break

        esc = value[i]
        mapping = {
            "0": "\0",
            "b": "\b",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "Z": "\x1a",
            "\\": "\\",
            "'": "'",
            '"': '"',
        }
        out.append(mapping.get(esc, esc))
        i += 1
    return "".join(out)


def parse_sql_tuples(values_sql: str) -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    row: list[str | None] | None = None
    field_chars: list[str] = []
    in_string = False
    in_row = False
    i = 0

    while i < len(values_sql):
        ch = values_sql[i]

        if in_string:
            if ch == "\\" and i + 1 < len(values_sql):
                field_chars.append(ch)
                field_chars.append(values_sql[i + 1])
                i += 2
                continue
            if ch == "'":
                in_string = False
                i += 1
                continue
            field_chars.append(ch)
            i += 1
            continue

        if ch == "(":
            in_row = True
            row = []
            field_chars = []
            i += 1
            continue

        if not in_row:
            i += 1
            continue

        if ch == "'":
            in_string = True
            i += 1
            continue

        if ch == ",":
            assert row is not None
            token = "".join(field_chars).strip()
            row.append(parse_field_token(token))
            field_chars = []
            i += 1
            continue

        if ch == ")":
            assert row is not None
            token = "".join(field_chars).strip()
            row.append(parse_field_token(token))
            rows.append(row)
            row = None
            field_chars = []
            in_row = False
            i += 1
            continue

        field_chars.append(ch)
        i += 1

    return rows


def parse_field_token(token: str) -> str | None:
    if not token or token.upper() == "NULL":
        return None

    if token.startswith("_binary "):
        token = token[len("_binary ") :].lstrip()

    if token.startswith("'") and token.endswith("'"):
        token = token[1:-1]

    return mysql_unescape(token)


def reconstruct_url_from_domain_index(domain_index: str | None, path: str | None) -> str | None:
    if not domain_index or not path:
        return None

    if not URL_RE.match(domain_index):
        return None

    scheme, remainder = domain_index.split("://", 1)
    remainder = remainder.rstrip(".")
    labels = [part for part in remainder.split(".") if part]
    if not labels:
        return None

    host = ".".join(reversed(labels))
    if not path.startswith("/"):
        path = "/" + path
    return f"{scheme}://{host}{path}"


def row_to_url(row: list[str | None]) -> str | None:
    # Newer schemas (>= 1.41) store domain and path separately.
    if len(row) >= 4:
        candidate = reconstruct_url_from_domain_index(row[-2], row[-1])
        if candidate:
            return candidate

    # Older schemas store the actual URL directly in column 3 (0-based index 2).
    if len(row) >= 3 and row[2] and URL_RE.match(row[2]):
        return row[2]

    return None


def main() -> None:
    args = parse_args()
    input_path: Path = args.input_path
    output_path: Path = args.output_path
    progress_every: int = args.progress_every

    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    line_count = 0
    insert_count = 0
    row_count = 0
    url_count = 0

    with open_text_for_read(input_path) as src, open_text_for_write(output_path) as dst:
        for raw_line in src:
            line_count += 1
            if not raw_line.startswith(INSERT_PREFIX):
                continue

            insert_count += 1
            values_sql = raw_line[len(INSERT_PREFIX) :].rstrip()
            if values_sql.endswith(";"):
                values_sql = values_sql[:-1]

            rows = parse_sql_tuples(values_sql)
            row_count += len(rows)

            for row in rows:
                url = row_to_url(row)
                if not url:
                    continue
                dst.write(url)
                dst.write("\n")
                url_count += 1

                if progress_every > 0 and url_count % progress_every == 0:
                    print(
                        f"Extracted {url_count:,} URLs after {line_count:,} lines, "
                        f"{insert_count:,} INSERT statements, {row_count:,} rows"
                    )

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Lines read: {line_count:,}")
    print(f"INSERT statements parsed: {insert_count:,}")
    print(f"Rows parsed: {row_count:,}")
    print(f"URLs written: {url_count:,}")


if __name__ == "__main__":
    main()
