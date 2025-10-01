import gzip
import io
from collections import defaultdict

from pyoxigraph import RdfFormat, parse


def open_fast_gzip_lines(path):
    f = gzip.open(path, "rb")  # binary mode
    buffered = io.BufferedReader(f, buffer_size=1024 * 1024)  # 1MB buffer
    # return io.TextIOWrapper(buffered, encoding='utf-8', errors='ignore')
    return io.TextIOWrapper(buffered, encoding="utf-8")


def parse_subject_block(subject, buffer):
    """
    triples: list of raw N-Triples lines (strings) for a single subject
    Returns: list of (predicate, object) pairs
    """
    triple_block = "\n".join(buffer)
    parsed = list(parse(triple_block.encode(), format=RdfFormat.N_TRIPLES))
    # print(parsed)
    d = defaultdict(list)
    for t in parsed:
        if t.subject.value != subject:
            continue
        d[t.predicate.value].append(t.object.value)
    return dict(d)


def stream_triples(filename, gzip=False):
    if gzip:
        reader = open_fast_gzip_lines(filename)
    else:
        reader = open(filename, "r", buffering=1 << 20)

    current_subject = None
    buffer = []

    with reader as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Extract subject string from line (manually, fast)
            if line.startswith("<"):
                subj_end = line.find(">")
                subject = line[1:subj_end]
            else:
                continue  # skip malformed line

            # skip empty
            if len(subject) <= 54:
                continue

            # New subject boundary?
            if subject != current_subject:
                if current_subject is not None and buffer:
                    props = parse_subject_block(current_subject, buffer)
                    yield current_subject, props

                current_subject = subject
                buffer = []

            buffer.append(line)

        if current_subject and buffer:
            props = parse_subject_block(current_subject, buffer)
            yield subject, props
