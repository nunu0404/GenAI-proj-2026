"""비교·표·그래프 형태: 수식 평가기 안전성, 좌표 계산, 런타임 저장, 편집."""
import math

import pytest

from app.chartmath import ExprError, parse_expr, sample
from app.providers.mock import MockImageProvider
from conftest import wait_for


@pytest.mark.parametrize("expr", ["__import__('os')", "x.__class__", "(lambda y: y)(x)", "open('f')", "max(x, key=abs)",
                                  "y + 1", "x if x else 1", "[x]", "'a'", "True", "x" * 100])
def test_expression_whitelist_rejects(expr):
    with pytest.raises(ExprError):
        parse_expr(expr)


def test_sampling_values():
    pts = sample("1/(1+exp(-x))", -6, 6, n=13)
    assert pts[6] == [0.0, 0.5] and pts[0][1] < 0.01 and pts[-1][1] > 0.99
    assert sample("x^2", -2, 2, n=5)[0][1] == 4.0
    pts = sample("log(x)", -1, 10, n=12)  # 음수 구간은 정의되지 않음 → None 으로 끊김
    assert pts[0][1] is None and pts[-1][1] == pytest.approx(math.log(10), rel=1e-6)
    with pytest.raises(ExprError):
        sample("sqrt(x)", -10, -1)


@pytest.mark.asyncio
async def test_structured_visual_slides_skip_image(make_rt):
    img = MockImageProvider(delay_ms=0)
    rt = make_rt(image=img)
    reqs = {"title_comparison": "다음 슬라이드에서는 과적합과 과소적합을 비교해서 설명하겠습니다",
            "title_table": "다음 슬라이드에서는 규제 방법들을 표로 정리하겠습니다",
            "title_chart": "다음 슬라이드에서는 시그모이드 함수를 그래프로 보여주세요"}
    for layout, text in reqs.items():
        await rt.manual_input(text, "force")
        await wait_for(lambda: rt.db.list_jobs(rt.sid)[0]["status"] == "ready")
        s = rt.db.list_slides(rt.sid)[-1]
        assert s["layout"] == layout and s["status"] == "ready" and not s["image_path"], layout
        assert s["visual"]["type"] == layout.split("_")[1]
    chart = rt.db.list_slides(rt.sid)[-1]["visual"]
    assert chart["kind"] == "function" and len(chart["computed"]) == 2
    assert chart["computed"][0]["points"][60] == [0.0, 0.5]  # 서버가 계산한 좌표
    assert img.calls == 0
    # 표 편집
    from app.schemas import SlideEdit
    table = rt.db.list_slides(rt.sid)[-2]
    await rt.edit_slide(table["id"], SlideEdit(table={"columns": ["A", "B"], "rows": [["1", "2"], ["3", "4"]]}))
    assert rt.db.get_slide(table["id"])["visual"] == {"type": "table", "columns": ["A", "B"], "rows": [["1", "2"], ["3", "4"]]}
    with pytest.raises(ValueError):
        SlideEdit(table={"columns": ["A", "B"], "rows": [["1"], ["3", "4"]]})
    from app.hub import serialize_slide
    assert serialize_slide(rt.db.get_slide(table["id"]), audience=True)["visual"]["type"] == "table"


def test_visual_column_migration(tmp_path):
    import sqlite3

    from app.db import SCHEMA, Database
    p = tmp_path / "old.sqlite3"
    con = sqlite3.connect(p)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO sessions(id,title,audience,created_at,updated_at) VALUES('ses_000000000002','t','a',0,0)")
    con.execute("INSERT INTO slides(id,session_id,position,layout,status,created_at,updated_at) "
                "VALUES('sld_2','ses_000000000002',0,'cover','ready',0,0)")
    con.commit()
    con.close()
    db = Database(p)
    assert db.list_slides("ses_000000000002")[0]["visual"] is None
    db.close()
