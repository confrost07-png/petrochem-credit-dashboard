"""Streamlit 버전 차이 흡수.

맥 기본 파이썬 3.9에서는 Streamlit 1.50까지만 설치된다. 1.50의 st.plotly_chart에는
width 인자가 없어 width="stretch"를 넘기면 화면에 노란 경고가 뜬다.
이 경우에만 width를 use_container_width로 바꿔 넘긴다. 최신 Streamlit에서는 아무것도 바꾸지 않는다.
"""
import inspect

import streamlit as st


def _patch_plotly_chart() -> None:
    original = st.plotly_chart
    if getattr(original, "_compat_patched", False):
        return
    try:
        params = inspect.signature(original).parameters
    except (TypeError, ValueError):
        return
    if "width" in params:
        return

    def plotly_chart(figure_or_data, *args, width=None, **kwargs):
        if width is not None:
            kwargs.setdefault("use_container_width", width == "stretch")
        return original(figure_or_data, *args, **kwargs)

    plotly_chart._compat_patched = True
    st.plotly_chart = plotly_chart


_patch_plotly_chart()
