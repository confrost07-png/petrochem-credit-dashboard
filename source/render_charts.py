"""metrics.csv에서 보고서·발표용 PNG 차트를 생성한다."""
from __future__ import annotations  # 파이썬 3.9에서도 X | None 표기 허용

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUT = ROOT / "output" / "charts"
COLORS = {"롯데케미칼": "#2455A4", "대한유화": "#E4873A", "금호석유화학": "#168A78"}


def font_setup() -> None:
    """Windows 맑은 고딕, macOS 애플고딕, 그 밖(리눅스·코랩)은 설치된 한글 글꼴을 찾아 쓴다."""
    import platform
    from matplotlib import font_manager
    if platform.system() == "Windows":
        plt.rcParams["font.family"] = "Malgun Gothic"
    elif platform.system() == "Darwin":
        plt.rcParams["font.family"] = "AppleGothic"
    else:
        installed = {f.name for f in font_manager.fontManager.ttflist}
        for name in ["NanumGothic", "Noto Sans CJK KR", "Noto Sans KR", "UnDotum"]:
            if name in installed:
                plt.rcParams["font.family"] = name
                break
        else:
            print("[주의] 한글 글꼴이 없어 글자가 깨질 수 있습니다. 코랩: !apt-get -qq install fonts-nanum 후 런타임 재시작")
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = 11


def plot_trend(frame: pd.DataFrame, field: str, title: str, unit: str, filename: str,
               reference: float | None = None) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.1))
    periods = ["2021", "2022", "2023", "2024", "2025", "2026H1"]
    for corp, color in COLORS.items():
        sub = frame[frame.corp_name == corp].set_index("period").reindex(periods)
        y = sub[field].tolist()
        ax.plot(periods[:5], y[:5], color=color, marker="o", linewidth=2.5, label=corp)
        ax.plot(periods[4:], y[4:], color=color, marker="D", linestyle="--", linewidth=2)
    if reference is not None:
        ax.axhline(reference, color="#C63838", linestyle=":", linewidth=1.6, label=f"참고선 {reference:g}{unit}")
    ax.set_title(title, fontsize=17, weight="bold", loc="left", pad=16)
    ax.set_ylabel(unit)
    ax.grid(axis="y", alpha=.22)
    ax.legend(frameon=False, ncol=2, loc="best")
    ax.text(0, -.18, "2026H1: 반기 누적, 점선으로 구분 | 출처: OpenDART 연결재무제표 | 참고선은 실제 은행 심사 기준이 아님",
            transform=ax.transAxes, fontsize=8, color="#52657D")
    fig.tight_layout()
    fig.savefig(OUT / filename, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_stability(frame: pd.DataFrame) -> None:
    selected = frame[frame.period == "2026H1"].set_index("corp_name").reindex(COLORS)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.1))
    for ax, field, title in zip(axes, ["debt_ratio", "borrow_dep"], ["부채비율", "차입금 의존도"]):
        ax.bar(selected.index, selected[field], color=list(COLORS.values()), width=.58)
        ax.set_title(f"2026H1 {title}", fontsize=16, weight="bold", loc="left", pad=15)
        ax.set_ylabel("%")
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        if field == "borrow_dep":
            ax.axhline(30, color="#C63838", linestyle=":", label="참고선 30%")
            ax.legend(frameon=False)
        for i, value in enumerate(selected[field]):
            if pd.notna(value):
                ax.text(i, value, f"{value:.1f}%", ha="center", va="bottom", fontsize=10)
    fig.text(.06, .02, "2026-06-30 시점 | 출처: OpenDART 연결재무제표 | 참고선은 실제 은행 심사 기준이 아님",
             fontsize=8, color="#52657D")
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(OUT / "stability_2026H1.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_quarter(frame: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.1))
    periods = ["2025Q1", "2026Q1", "2025Q2", "2026Q2"]
    for corp, color in COLORS.items():
        sub = frame[frame.corp_name == corp].set_index("period").reindex(periods)
        axes[0].plot(periods, sub.revenue / 100_000_000, marker="o", color=color, label=corp, linewidth=2)
        axes[1].plot(periods, sub.op_margin, marker="o", color=color, label=corp, linewidth=2)
    for ax, title, unit in zip(axes, ["분기 매출액", "분기 영업이익률"], ["억원", "%"]):
        ax.set_title(title, fontsize=16, weight="bold", loc="left", pad=15)
        ax.set_ylabel(unit)
        ax.grid(axis="y", alpha=.22)
        ax.tick_params(axis="x", labelrotation=30)
        ax.axvspan(2.5, 3.5, color="#F9E4E4", alpha=.45)
    axes[0].legend(frameon=False)
    fig.text(.06, .02, "핵심: 2026Q2 vs 2025Q2 | 출처: OpenDART 연결재무제표 | 분기 수치는 일회성·계절성 영향 가능",
             fontsize=8, color="#52657D")
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(OUT / "quarter_comparison.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_borrow(frame: pd.DataFrame) -> None:
    """차입금 의존도 추이와 30% 참고선."""
    plot_trend(frame, "borrow_dep", "차입금 의존도 (차입금 ÷ 자산총계)", "%", "borrow_dependence.png", 30)


def plot_credit_map(frame: pd.DataFrame) -> None:
    """여신 관리 지도: 이자보상배율(가로) × 차입금 의존도(세로), 2021→2026H1 궤적."""
    lo, hi = -5, 15
    periods = ["2021", "2022", "2023", "2024", "2025", "2026H1"]
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    quads = [(lo, 1, 0, 30, "#FFF4E6", "관리 강화"), (1, hi, 0, 30, "#EBFBEE", "정상 관리"),
             (lo, 1, 30, 40, "#FFE3E3", "집중 관리"), (1, hi, 30, 40, "#FFF9DB", "관찰")]
    for x0, x1, y0, y1, color, name in quads:
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, color=color, zorder=0))
        ax.text(x0 + .3, y1 - 1.3, name, fontsize=12, weight="bold", color="#4A5568", va="top")
    ax.axvline(1, color="#C63838", linestyle=":", linewidth=1.5)
    ax.axhline(30, color="#C63838", linestyle=":", linewidth=1.5)
    for corp, color in COLORS.items():
        sub = frame[frame.corp_name == corp].set_index("period").reindex(periods)
        xs = sub.icr.clip(lo + .3, hi - .3).tolist()
        ys = sub.borrow_dep.tolist()
        ax.plot(xs, ys, color=color, linewidth=1.6, alpha=.75, marker="o", markersize=5)
        for k, (p, x, y, raw) in enumerate(zip(periods, xs, ys, sub.icr.tolist())):
            label = ("'" + p[2:4]) if p != "2026H1" else "26H1"
            if raw > hi or raw < lo:
                label += f" ({raw:.1f}배)"
            ax.annotate(label, (x, y), textcoords="offset points", xytext=(5, 4) if k % 2 == 0 else (5, -12), fontsize=8, color=color)
        ax.scatter([xs[-1]], [ys[-1]], s=150, facecolors="white", edgecolors=color, linewidths=2.4, zorder=5, label=corp)
    ax.set_xlim(lo, hi)
    ax.set_ylim(0, 40)
    ax.set_xlabel("이자보상배율† (배)  ← 이자를 못 냄 · 이자를 감당함 →")
    ax.set_ylabel("차입금 의존도 (%)")
    ax.set_title("여신 관리 지도: 2021 → 2026 상반기", fontsize=17, weight="bold", loc="left", pad=16)
    ax.legend(frameon=False, loc="upper right")
    ax.text(0, -.14, "점선 = 참고선(1배, 30%) · 빈 원 = 2026 상반기 · 축 밖 값은 가장자리에 두고 괄호에 실제 값 · †금융원가 기준 · 실제 은행 심사 기준이 아님",
            transform=ax.transAxes, fontsize=8, color="#52657D")
    fig.tight_layout()
    fig.savefig(OUT / "credit_map.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    if (DATA / ".sample_data").exists():
        raise SystemExit("샘플 데이터로 제출용 차트를 만들 수 없습니다.")
    font_setup()
    OUT.mkdir(parents=True, exist_ok=True)
    metrics = pd.read_csv(DATA / "metrics.csv", dtype={"period": str})
    quarterly = pd.read_csv(DATA / "quarterly_metrics.csv", dtype={"period": str})
    # 보고서·발표 차트는 분석 대상 3사만 그린다 (확장 기업은 앱 전용)
    metrics = metrics[metrics.corp_name.isin(COLORS)]
    quarterly = quarterly[quarterly.corp_name.isin(COLORS)]
    plot_trend(metrics, "sales_growth", "매출 성장률", "%", "sales_growth.png", 0)
    plot_trend(metrics, "op_margin", "영업이익률", "%", "op_margin.png", 0)
    plot_trend(metrics, "icr", "이자보상배율† (영업이익 ÷ 금융원가)", "배", "interest_coverage.png", 1)
    plot_borrow(metrics)
    plot_credit_map(metrics)
    plot_stability(metrics)
    plot_quarter(quarterly)
    print(f"차트 7개 저장: {OUT}")


if __name__ == "__main__":
    main()
