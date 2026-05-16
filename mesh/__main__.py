"""python -m mesh <bench|publish|demo|node> ..."""

import sys

_USAGE = """Usage:
  python -m mesh bench [--events PATH] [--localizations PATH]
  python -m mesh publish --events PATH [--localizations PATH]
  python -m mesh demo [--events PATH] [--localizations PATH]
  python -m mesh node --id drone_1|drone_2|drone_3|operator
"""


def main() -> int:
    if len(sys.argv) < 2:
        print(_USAGE, file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "bench":
        from .bench_bandwidth import main as bench_main
        return bench_main(rest)
    if cmd == "publish":
        from .publish import _cli
        return _cli(rest)
    if cmd == "demo":
        from .demo import main as demo_main
        return demo_main(rest)
    if cmd == "node":
        from .node import run_node
        return run_node(rest)
    print(f"Unknown subcommand: {cmd}\n{_USAGE}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
