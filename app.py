import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import streamlit as st

from gep_integration import (
    build_capsule_asset,
    build_evolution_event,
    record_agent_turn,
    run_evolver_once,
)


BASE_DIR = Path(__file__).resolve().parent
STATE_PATH = BASE_DIR / "data" / "demo_state.json"
KNOWLEDGE_PATH = BASE_DIR / "data" / "knowledge.json"
RULES_PATH = BASE_DIR / "data" / "rules.json"
GOLDEN_CASES_PATH = BASE_DIR / "data" / "golden_cases.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


KNOWLEDGE = load_json(KNOWLEDGE_PATH)
RULES = load_json(RULES_PATH)
GOLDEN_CASES = load_json(GOLDEN_CASES_PATH)
SOURCE_KNOWLEDGE = KNOWLEDGE[0]
SIMILAR_KNOWLEDGE = KNOWLEDGE[1]

SOURCE_QUERY = SOURCE_KNOWLEDGE["questions"][0]
SIMILAR_QUERY = SIMILAR_KNOWLEDGE["questions"][-1]
INITIAL_ANSWER = SOURCE_KNOWLEDGE["answer"]
DEFAULT_CORRECTION = (
    "不要直接把问题归为机器故障。应按顺序排查：新机运输螺栓是否拆除、"
    "地面是否坚硬平整且脚垫已调平、衣物是否缠绕偏载。"
    "若空桶仍剧烈跳动，或伴随异响、漏水、焦味，应停止使用并转人工，"
    "不得承诺维修、赔付或上门结果。"
)
EVOLVED_ANSWER = """先别急着判断机器坏了，可以按下面顺序检查：

1. **运输螺栓**：如果是新机，确认背部运输螺栓已经全部拆除。
2. **地面与脚垫**：机器应放在坚硬、平整的地面，四个脚垫都要稳定着地。
3. **衣物偏载**：暂停脱水，把缠绕或堆在一侧的衣物抖散后均匀放回。

完成后可少量放衣物再试一次。若**空桶仍剧烈跳动**，或伴随异响、漏水、焦味，请停止使用并转人工进一步核实。"""
HIGH_RISK_ANSWER = """请立即**断电并停止使用**，不要继续空转或自行拆机。

您描述的晃动同时伴随漏水、焦味、冒烟、漏电或明显异响，已经超出普通自助排查范围。请保留现场视频、机器铭牌和订单信息，联系人工售后进一步核实。

当前不能仅凭现象直接判断质量责任，也不能提前承诺维修、赔付、退款、换货或上门结果。"""
FALLBACK_ANSWER = "当前演示只覆盖洗衣机或脱水机的脱水晃动问题，请转人工客服进一步确认。"

INITIAL_STATE = {
    "session": {
        "source_query": "",
        "source_answer": "",
        "source_knowledge": {},
        "similar_query": "",
        "similar_answer": "",
    },
    "review": {
        "marked_for_evolution": False,
        "correction": "",
        "candidate_generated": False,
    },
    "capsule": {
        "id": "CAP-WM-001",
        "title": "洗衣机脱水乱跳结构化排查",
        "status": "未生成",
        "source": "智能客服1.0真实问法 + 人工纠正",
        "source_refs": [
            "03_清洗成果/智能客服1.0.xlsx｜模板!A23:B23",
            "03_清洗成果/智能客服2.0.xlsx｜模板!A65:B65",
        ],
        "trigger": "洗衣机在脱水阶段明显晃动、跳动或移位",
        "steps": [
            "确认新机运输螺栓是否已拆除",
            "确认机器是否放在坚硬、平整的地面并调平脚垫",
            "暂停后将缠绕或偏在一侧的衣物抖散、均匀放置",
            "空桶仍剧烈跳动、出现异响或漏水时停止使用并转人工",
        ],
        "boundary": "不承诺故障结论、赔付或上门结果；存在异响、漏水、焦味或空桶剧烈跳动时转人工。",
        "reuse_count": 0,
        "human_approved": False,
        "approved_by": "",
        "approved_at": "",
        "gep_asset_id": "",
        "gep_status": "等待黄金测试验证",
        "validation": {
            "status": "未运行",
            "passed": 0,
            "total": len(GOLDEN_CASES),
            "pass_rate": 0,
            "validated_at": "",
            "results": [],
        },
    },
    "evolver": {
        "last_status": "未运行",
        "last_output": "",
    },
    "events": [],
}


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def initial_state() -> dict:
    return deepcopy(INITIAL_STATE)


def load_state(path: Path = STATE_PATH) -> dict:
    with path.open("r", encoding="utf-8") as file:
        state = json.load(file)
    state.setdefault("session", {})
    state["session"].setdefault("source_knowledge", {})
    state.setdefault("capsule", {})
    state["capsule"].setdefault("source_refs", INITIAL_STATE["capsule"]["source_refs"])
    state["capsule"].setdefault("human_approved", False)
    state["capsule"].setdefault("approved_by", "")
    state["capsule"].setdefault("approved_at", "")
    state["capsule"].setdefault("gep_asset_id", "")
    state["capsule"].setdefault("gep_status", "等待黄金测试验证")
    state["capsule"].setdefault(
        "validation", deepcopy(INITIAL_STATE["capsule"]["validation"])
    )
    state.setdefault(
        "evolver",
        {
            "last_status": "未运行",
            "last_output": "",
        },
    )
    return state


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def add_event(state: dict, event_type: str, title: str, detail: str) -> None:
    state["events"].append(
        {
            "type": event_type,
            "title": title,
            "detail": detail,
            "time": now_text(),
        }
    )


def is_shaking_query(query: str) -> bool:
    appliance_terms = ("洗衣机", "脱水机", "机器", "甩干", "脱水", "空桶")
    shaking_terms = ("乱跳", "跳", "抖", "晃", "移位", "震动", "不稳", "跑来跑去")
    return any(term in query for term in appliance_terms) and any(
        term in query for term in shaking_terms
    )


def answer_query(state: dict, query: str) -> tuple[str, bool]:
    if not state["capsule"].get("human_approved") or not is_shaking_query(query):
        return FALLBACK_ANSWER, False
    if any(word in query for word in ("焦味", "冒烟", "漏电", "漏水", "异响")):
        return HIGH_RISK_ANSWER, True
    return EVOLVED_ANSWER, True


def submit_source_query(state: dict, query: str) -> None:
    state["session"]["source_query"] = query
    state["session"]["source_answer"] = INITIAL_ANSWER
    state["session"]["source_knowledge"] = {
        "id": SOURCE_KNOWLEDGE["id"],
        "label": SOURCE_KNOWLEDGE["label"],
        "source_file": SOURCE_KNOWLEDGE["source_file"],
        "source_sheet": SOURCE_KNOWLEDGE["source_sheet"],
        "source_row": SOURCE_KNOWLEDGE["source_row"],
    }
    if not any(event["type"] == "发现" for event in state["events"]):
        add_event(
            state,
            "发现",
            "真实旧知识暴露缺口",
            f'命中 {SOURCE_KNOWLEDGE["id"]}，缺少运输固定件检查和完整风险边界。',
        )
    record_agent_turn("user", query, "customer_query")
    record_agent_turn("assistant", INITIAL_ANSWER, "initial_answer")


def mark_for_evolution(state: dict) -> None:
    state["review"]["marked_for_evolution"] = True
    if not any(event["type"] == "标记" for event in state["events"]):
        add_event(state, "标记", "值得进化", "人工发现回答可执行性不足。")


def submit_correction(state: dict, correction: str) -> None:
    state["review"]["correction"] = correction.strip()
    if not any(event["type"] == "纠正" for event in state["events"]):
        add_event(state, "纠正", "人工补充排查路径", correction.strip())
    record_agent_turn("user", correction, "human_correction")


def generate_candidate(state: dict) -> None:
    state["review"]["candidate_generated"] = True
    state["capsule"]["status"] = "待批准"
    state["capsule"]["gep_status"] = "候选经验尚未验证，不生成正式 GEP Capsule"
    if not any(event["type"] == "生成" for event in state["events"]):
        add_event(
            state,
            "生成",
            "候选 Capsule 已生成",
            "提炼运输螺栓、地面、衣物偏载和转人工边界。",
        )


def approve_capsule(state: dict, approved_by: str = "业务审核人") -> None:
    state["capsule"]["status"] = "待验证"
    state["capsule"]["human_approved"] = True
    state["capsule"]["approved_by"] = approved_by
    state["capsule"]["approved_at"] = now_text()
    result = build_evolution_event(
        state["capsule"],
        signal="human_approval",
        source_type="user_authored",
        score=1,
    )
    if not result.get("ok"):
        state["capsule"]["gep_status"] = f'事件记录失败：{result.get("error", "未知错误")}'
    if not any(event["type"] == "批准" for event in state["events"]):
        add_event(
            state,
            "批准",
            "候选 Capsule 已批准进入验证",
            f"{approved_by} 已批准复用测试，但尚未证明效果。",
        )
    record_agent_turn("assistant", "候选 Capsule 已通过人工批准，等待验证。", "human_approval")


def submit_similar_query(state: dict, query: str) -> bool:
    answer, reused = answer_query(state, query)
    state["session"]["similar_query"] = query
    state["session"]["similar_answer"] = answer
    if reused:
        state["capsule"]["reuse_count"] += 1
        add_event(state, "复用", "相似问题命中新经验", query)
        result = build_evolution_event(
            state["capsule"],
            signal="capsule_reused",
            source_type="reused",
            score=0.95,
        )
        if not result.get("ok"):
            state["capsule"]["gep_status"] = f'复用事件记录失败：{result.get("error", "未知错误")}'
    record_agent_turn("user", query, "similar_query")
    record_agent_turn("assistant", answer, "capsule_reused" if reused else "fallback_answer")
    return reused


def run_golden_validation(state: dict) -> dict:
    results = []
    for case in GOLDEN_CASES:
        answer, reused = answer_query(state, case["query"])
        concept_checks = [
            any(term in answer for term in alternatives)
            for alternatives in case["required_concepts"]
        ]
        passed = reused == case["expected_reuse"] and all(concept_checks)
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_reuse": case["expected_reuse"],
                "actual_reuse": reused,
                "concept_checks": concept_checks,
                "passed": passed,
            }
        )

    passed_count = sum(result["passed"] for result in results)
    total = len(results)
    pass_rate = passed_count / total if total else 0
    validation = {
        "status": "通过" if passed_count == total else "未通过",
        "passed": passed_count,
        "total": total,
        "pass_rate": pass_rate,
        "validated_at": now_text(),
        "results": results,
    }
    state["capsule"]["validation"] = validation

    if passed_count == total:
        asset_result = build_capsule_asset(
            state["capsule"],
            state["review"]["correction"],
            validation_score=pass_rate,
            validation_summary=f"{passed_count}/{total} 条黄金测试通过",
        )
        if asset_result.get("ok"):
            state["capsule"]["status"] = "已验证"
            state["capsule"]["gep_asset_id"] = asset_result["asset"]["asset_id"]
            state["capsule"]["gep_status"] = "黄金测试通过，Schema 与哈希校验通过"
            build_evolution_event(
                state["capsule"],
                signal="golden_validation_passed",
                source_type="generated",
                score=pass_rate,
            )
        else:
            state["capsule"]["status"] = "验证通过，资产生成失败"
            state["capsule"]["gep_status"] = (
                f'生成失败：{asset_result.get("error", "未知错误")}'
            )
    else:
        state["capsule"]["status"] = "验证未通过"
        state["capsule"]["gep_status"] = "黄金测试未全部通过，不生成正式 GEP Capsule"

    add_event(
        state,
        "验证",
        f"黄金测试 {passed_count}/{total}",
        "全部通过并生成正式资产。"
        if passed_count == total
        else "存在失败样本，候选经验需要继续修改。",
    )
    record_agent_turn(
        "assistant",
        f"黄金测试结果：{passed_count}/{total}",
        "golden_validation",
    )
    return validation


def render_header() -> None:
    st.set_page_config(page_title="The Pearl", page_icon="🫧", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { background: #f7f9fc; }
        .block-container { padding-top: 2rem; max-width: 1180px; }
        .pearl-card {
            background: white; border: 1px solid #e5eaf2; border-radius: 16px;
            padding: 18px 20px; box-shadow: 0 6px 18px rgba(31, 48, 76, .05);
        }
        .eyebrow { color: #2864dc; font-weight: 700; letter-spacing: .08em; }
        .muted { color: #687386; }
        div[data-testid="stMetric"] {
            background: white; border: 1px solid #e5eaf2; padding: 12px 16px;
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="eyebrow">THE PEARL · SELF-EVOLVING SERVICE AGENT</div>', unsafe_allow_html=True)
    st.title("家电客服自进化 Agent")
    st.caption("真实旧知识 · 人工审核 · 黄金测试 · 已验证 Capsule · JSON 本地持久化")


def render_chat_tab(state: dict) -> None:
    st.subheader("客户聊天")
    st.caption("先发送首次咨询；经验批准后，再发送相似咨询观察回答变化。")

    left, right = st.columns(2)
    with left:
        st.markdown("#### ① 首次咨询")
        source_query = st.text_input("客户问题", SOURCE_QUERY, key="source_query_input")
        if st.button("发送首次咨询", type="primary", use_container_width=True):
            submit_source_query(state, source_query)
            save_state(state)
            st.rerun()
        if state["session"]["source_query"]:
            with st.chat_message("user"):
                st.write(state["session"]["source_query"])
            with st.chat_message("assistant"):
                st.write(state["session"]["source_answer"])
            source = state["session"]["source_knowledge"]
            st.caption(
                f'命中真实知识：{source.get("id")}｜{source.get("label")}｜'
                f'{source.get("source_file")} · {source.get("source_sheet")}!{source.get("source_row")}'
            )
            st.warning("缺口：没有检查运输固定件，排查顺序和高风险边界也不完整。")

    with right:
        st.markdown("#### ② 相似问题复用")
        similar_query = st.text_input("下一位客户的问题", SIMILAR_QUERY, key="similar_query_input")
        approved = state["capsule"].get("human_approved", False)
        if st.button(
            "发送相似咨询",
            disabled=not approved,
            use_container_width=True,
            help=None if approved else "请先在人工审核中批准 Capsule",
        ):
            reused = submit_similar_query(state, similar_query)
            save_state(state)
            if reused:
                st.toast("已命中新版 Capsule")
            st.rerun()
        if not approved:
            st.info("Capsule 尚未批准，相似问题复用入口暂未开放。")
        if state["session"]["similar_query"]:
            with st.chat_message("user"):
                st.write(state["session"]["similar_query"])
            with st.chat_message("assistant"):
                st.markdown(state["session"]["similar_answer"])
            st.success(
                f'已复用 {state["capsule"]["id"]}：排查更具体，风险边界更清楚。'
            )


def render_review_tab(state: dict) -> None:
    st.subheader("人工审核")
    if not state["session"]["source_query"]:
        st.info("请先在“客户聊天”发送首次咨询。")
        return

    st.markdown("#### 初始回答")
    st.markdown(f'<div class="pearl-card">{state["session"]["source_answer"]}</div>', unsafe_allow_html=True)

    if not state["review"]["marked_for_evolution"]:
        if st.button("标记为值得进化", type="primary"):
            mark_for_evolution(state)
            save_state(state)
            st.rerun()
        return
    st.success("已标记为值得进化")

    correction = st.text_area(
        "人工补充纠正",
        value=state["review"]["correction"] or DEFAULT_CORRECTION,
        height=150,
    )
    correction_saved = bool(state["review"]["correction"])
    if not correction_saved:
        if st.button("保存人工纠正", type="primary"):
            if correction.strip():
                submit_correction(state, correction)
                save_state(state)
                st.rerun()
            else:
                st.error("人工纠正不能为空。")
        return
    st.success("人工纠正已保存")

    if not state["review"]["candidate_generated"]:
        if st.button("生成候选 Capsule", type="primary"):
            generate_candidate(state)
            save_state(state)
            st.rerun()
        return

    capsule = state["capsule"]
    st.markdown("#### 候选 Capsule")
    st.markdown(
        f"""
        <div class="pearl-card">
        <b>{capsule["id"]} · {capsule["title"]}</b><br><br>
        <span class="muted">来源</span>　{capsule["source"]}<br>
        <span class="muted">触发条件</span>　{capsule["trigger"]}<br>
        <span class="muted">适用边界</span>　{capsule["boundary"]}<br>
        <span class="muted">当前状态</span>　{capsule["status"]}
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("来源证据与已确认规则"):
        for source_ref in capsule["source_refs"]:
            st.write(f"- {source_ref}")
        for rule in RULES:
            st.write(
                f'- {rule["rule_id"]}｜{rule["rule"]}｜'
                f'状态：{rule["approval_status"]}'
            )
    for index, step in enumerate(capsule["steps"], 1):
        st.write(f"{index}. {step}")

    if not capsule.get("human_approved"):
        if st.button("批准 Capsule", type="primary"):
            approve_capsule(state)
            save_state(state)
            st.rerun()
    else:
        st.success(
            f'已由 {capsule["approved_by"]} 批准进入测试；'
            f'当前状态：{capsule["status"]}。'
        )


def render_dashboard_tab(state: dict) -> None:
    st.subheader("进化看板")
    capsule = state["capsule"]
    completed_types = {event["type"] for event in state["events"]}

    validation = capsule["validation"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Capsule 状态", capsule["status"])
    col2.metric("进化事件", len(state["events"]))
    col3.metric("新版经验复用", f'{capsule["reuse_count"]} 次')
    col4.metric(
        "黄金测试",
        f'{validation["passed"]}/{validation["total"]}',
    )

    st.markdown("#### EvoMap 接入状态")
    gep_ready = bool(capsule.get("gep_asset_id"))
    st.write(f'GEP SDK：{"✅ 已验证 Capsule" if gep_ready else capsule["gep_status"]}')
    if gep_ready:
        st.code(capsule["gep_asset_id"], language=None)
    st.write("Evolver：离线会话解析 · observe-only · 不连接 Hub")
    if st.button("运行一次 Evolver 会话分析", disabled=not state["events"]):
        with st.spinner("Evolver 正在解析脱敏会话记录…"):
            result = run_evolver_once()
        state["evolver"]["last_status"] = "成功" if result.get("ok") else "失败"
        state["evolver"]["last_output"] = result.get("output") or result.get("error", "")
        save_state(state)
        st.rerun()
    if state["evolver"]["last_status"] != "未运行":
        with st.expander(f'Evolver 最近运行：{state["evolver"]["last_status"]}'):
            st.code(state["evolver"]["last_output"] or "无输出", language=None)

    st.markdown("#### 进化路径")
    stages = ["发现", "标记", "纠正", "生成", "批准", "复用", "验证"]
    stage_cols = st.columns(len(stages))
    for column, stage in zip(stage_cols, stages):
        with column:
            st.markdown(f"### {'✅' if stage in completed_types else '○'}")
            st.caption(stage)

    if state["events"]:
        st.markdown("#### Evolution Events")
        for event in reversed(state["events"]):
            with st.expander(f'{event["type"]} · {event["title"]} · {event["time"]}'):
                st.write(event["detail"])

    st.markdown("#### 黄金测试")
    if not capsule.get("human_approved"):
        st.info("人工批准后才能运行黄金测试。")
    elif st.button("运行 10 条黄金测试", type="primary"):
        run_golden_validation(state)
        save_state(state)
        st.rerun()

    if validation["status"] != "未运行":
        st.progress(validation["pass_rate"])
        st.caption(
            f'结果：{validation["status"]}｜'
            f'{validation["passed"]}/{validation["total"]}｜'
            f'验证时间：{validation["validated_at"]}'
        )
        for result in validation["results"]:
            icon = "✅" if result["passed"] else "❌"
            st.write(
                f'{icon} {result["id"]}｜{result["query"]}｜'
                f'预期复用：{result["expected_reuse"]}｜'
                f'实际复用：{result["actual_reuse"]}'
            )

    st.markdown("#### 进化前后对比")
    before, after = st.columns(2)
    with before:
        st.markdown("**进化前**")
        st.markdown(f'<div class="pearl-card">{INITIAL_ANSWER}</div>', unsafe_allow_html=True)
        st.caption("笼统建议 · 无明确顺序 · 边界不清")
    with after:
        st.markdown("**进化后**")
        if capsule.get("human_approved"):
            st.markdown(EVOLVED_ANSWER)
            st.caption("结构化排查 · 可执行 · 有转人工边界")
        else:
            st.markdown('<div class="pearl-card muted">批准 Capsule 后显示新版回答</div>', unsafe_allow_html=True)

    st.divider()
    if st.button("重置演示数据"):
        save_state(initial_state())
        st.rerun()


def main() -> None:
    render_header()
    state = load_state()
    chat_tab, review_tab, dashboard_tab = st.tabs(["客户聊天", "人工审核", "进化看板"])
    with chat_tab:
        render_chat_tab(state)
    with review_tab:
        render_review_tab(state)
    with dashboard_tab:
        render_dashboard_tab(state)


if __name__ == "__main__":
    main()
