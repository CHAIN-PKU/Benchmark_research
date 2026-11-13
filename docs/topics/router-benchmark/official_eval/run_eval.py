"""调用官方 run_evaluation，但先注册我们的适配层；不启动 nix_swe 容器（这批题用不到）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
import godog_v2  # noqa: F401  注册 cucumber/godog

from multi_swe_bench.harness.run_evaluation import CliArgs, get_parser

args = get_parser().parse_args()
CliArgs.from_dict(vars(args)).run()
