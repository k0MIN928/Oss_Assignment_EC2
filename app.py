import streamlit as st
import json
import os
import time
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="DS 직무 테스트",
    page_icon="🔬",
    layout="centered",
)

st.markdown(
    """
    <style>
    .info-banner {
        background-color: #1e293b;
        color: #f1f5f9 !important;
        padding: 1.2rem 1.5rem;
        border-radius: 0.6rem;
        text-align: center;
        margin-bottom: 1.2rem;
    }
    .info-banner * { color: #f1f5f9 !important; }

    .result-box {
        background-color: #0f172a;
        color: #f8fafc !important;
        padding: 2rem 1.5rem;
        border-radius: 0.8rem;
        text-align: center;
        margin: 1rem 0;
    }
    .result-box * { color: #f8fafc !important; }
    .result-box .big-emoji { font-size: 3.5rem; }

    .sub-result-box {
        background-color: #f1f5f9;
        color: #334155 !important;
        padding: 0.9rem 1.2rem;
        border-radius: 0.5rem;
        text-align: center;
        margin: 0.5rem 0;
    }
    .sub-result-box * { color: #334155 !important; }

    .tie-notice {
        background-color: #fef3c7;
        color: #92400e !important;
        padding: 0.9rem 1.2rem;
        border-radius: 0.5rem;
        text-align: center;
        margin: 0.5rem 0;
    }
    .tie-notice * { color: #92400e !important; }

    .skill-tag {
        display: inline-block;
        background-color: #e2e8f0;
        color: #334155;
        padding: 0.3rem 0.7rem;
        border-radius: 0.3rem;
        margin: 0.15rem;
        font-size: 0.88rem;
    }

    .step-item {
        background-color: #f8fafc;
        border-left: 3px solid #475569;
        padding: 0.7rem 1rem;
        margin: 0.3rem 0;
        border-radius: 0 0.4rem 0.4rem 0;
        color: #1e293b !important;
    }
    .step-item * { color: #1e293b !important; }

    .quiz-status {
        background-color: #f1f5f9;
        padding: 0.8rem 1.2rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        color: #334155 !important;
    }
    .quiz-status * { color: #334155 !important; }

    .history-item {
        border-left: 3px solid #475569;
        padding: 0.8rem 1.2rem;
        margin: 0.5rem 0;
        background-color: #fafafa;
        border-radius: 0 0.4rem 0.4rem 0;
        color: #1e293b !important;
    }
    .history-item * { color: #1e293b !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── 캐싱 함수 ──

@st.cache_data(show_spinner="퀴즈 데이터를 불러오는 중...")
def load_quiz_data():
    """퀴즈 문항과 결과 데이터를 JSON에서 읽어 캐싱합니다.
    매 rerun마다 디스크 I/O를 반복하지 않기 위해 캐싱을 적용합니다.
    최초 1회만 파일을 읽고, 이후에는 메모리 캐시에서 즉시 반환합니다.
    """
    path = os.path.join(os.path.dirname(__file__), "data", "quiz_data.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner="사용자 정보를 불러오는 중...")
def load_user_data():
    """사용자 인증 정보를 JSON에서 읽어 캐싱합니다."""
    path = os.path.join(os.path.dirname(__file__), "data", "users.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def compute_scores(answers_tuple, _n_questions):
    """답변 인덱스 튜플로부터 직무별 점수를 계산합니다.
    같은 답변 조합이면 캐시에서 즉시 반환합니다.
    """
    quiz = load_quiz_data()
    questions = quiz["questions"]
    keys = ["analyst", "scientist", "ml_engineer", "data_engineer", "ai_researcher"]
    scores = {k: 0 for k in keys}

    for i, ans in enumerate(answers_tuple):
        if ans is not None and i < len(questions):
            scores[questions[i]["options"][ans]["type"]] += 1

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return scores, ranked


@st.cache_data
def build_summary_text(scores_tuple):
    """결과 공유용 요약 텍스트를 생성하고 캐싱합니다."""
    quiz = load_quiz_data()
    results = quiz["results"]
    keys = ["analyst", "scientist", "ml_engineer", "data_engineer", "ai_researcher"]
    scores = dict(zip(keys, scores_tuple))
    total = sum(scores.values()) or 1
    lines = []
    for k in keys:
        pct = scores[k] / total * 100
        name = results[k]["title"].split(" (")[0]
        lines.append(f"{results[k]['emoji']} {name}: {pct:.0f}%")
    return "\n".join(lines)


# ── 세션 상태 ──

def init_session():
    for k, v in {
        "logged_in": False,
        "username": "",
        "display_name": "",
        "page": "home",
        "quiz_done": False,
        "scores": {},
        "ranked": [],
        "q_idx": 0,
        "answers": {},
        "history": [],
        "reg_users": {},
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session()

TYPE_KEYS = ["analyst", "scientist", "ml_engineer", "data_engineer", "ai_researcher"]


# ── 인증 ──

def authenticate(uid, pw):
    file_users = load_user_data().get("users", {})
    reg_users = st.session_state.reg_users

    if uid in file_users and file_users[uid]["password"] == pw:
        return True, file_users[uid]["name"]
    if uid in reg_users and reg_users[uid]["password"] == pw:
        return True, reg_users[uid]["name"]
    return False, ""


def go_to(page, **reset):
    st.session_state.page = page
    for k, v in reset.items():
        st.session_state[k] = v
    st.rerun()


# ── 사이드바 ──

def sidebar():
    with st.sidebar:
        st.markdown("### 메뉴")

        if st.button("홈", use_container_width=True):
            go_to("home")

        if st.button("직무 소개", use_container_width=True):
            go_to("jobs")

        if st.button("캐싱 시연", use_container_width=True):
            go_to("cache_demo")

        if st.session_state.logged_in:
            if st.button("테스트 시작", use_container_width=True):
                go_to("quiz", q_idx=0, answers={}, quiz_done=False)

            if st.session_state.history:
                if st.button("지난 기록", use_container_width=True):
                    go_to("history")

            st.markdown("---")
            st.write(f"**{st.session_state.display_name}** ({st.session_state.username})")

            if st.button("로그아웃", use_container_width=True):
                saved_reg = st.session_state.reg_users
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.session_state.reg_users = saved_reg
                init_session()
                st.rerun()
        else:
            if st.button("로그인", use_container_width=True):
                go_to("login")
            if st.button("회원가입", use_container_width=True):
                go_to("register")

        st.markdown("---")

        with st.expander("캐싱 상태"):
            st.caption("✅ `load_quiz_data()` — `@st.cache_data` 적용")
            st.caption("✅ `load_user_data()` — `@st.cache_data` 적용")
            st.caption(
                "JSON 파일을 매번 다시 읽지 않고 "
                "메모리 캐시에서 즉시 불러옵니다. "
                "자세한 내용은 '캐싱 시연' 페이지에서 확인하세요."
            )

        st.caption("권영민 | 광운대학교 · 오픈소스SW")


# ── 홈 ──

def page_home():
    st.markdown(
        '<div class="info-banner">'
        "<strong>오픈소스소프트웨어 중간 대체 과제</strong><br>"
        "학번: 2022603032 · 이름: 권영민"
        "</div>",
        unsafe_allow_html=True,
    )

    st.title("나에게 맞는 DS 직무는?")
    st.write(
        "데이터 사이언스 분야에도 여러 갈래가 있습니다. "
        "간단한 10문항 테스트로 내 성향에 가까운 직무를 알아보세요."
    )

    st.markdown("")
    cols = st.columns(5)
    previews = [
        ("📊", "분석가"),
        ("🔬", "사이언티스트"),
        ("⚙️", "ML 엔지니어"),
        ("🛠️", "데이터 엔지니어"),
        ("🧪", "AI 리서처"),
    ]
    for col, (icon, name) in zip(cols, previews):
        col.markdown(f"<div style='text-align:center'><span style='font-size:1.8rem'>{icon}</span><br><small>{name}</small></div>", unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("**진행 순서**")
    st.write("로그인 → 질문 10개 답변 → 직무 유형 확인 → 스킬·로드맵 추천")

    with st.expander("이 앱은 어떻게 작동하나요?"):
        st.markdown(
            "10개의 성향 질문에 답변하면, 각 선택지가 5개 직무(분석가·사이언티스트·ML엔지니어·데이터엔지니어·AI리서처) 중 "
            "하나에 점수를 부여합니다. 모든 문항을 마치면 점수를 합산하여 가장 높은 직무를 추천하고, "
            "레이더 차트·막대 차트로 적합도를 시각화합니다.\n\n"
            "**사용 기술:** Streamlit, Plotly, `@st.cache_data` 캐싱, `st.session_state` 상태 관리"
        )

    st.markdown("---")

    if not st.session_state.logged_in:
        st.info("먼저 로그인이 필요합니다.")
        c1, c2 = st.columns(2)
        if c1.button("로그인", use_container_width=True):
            go_to("login")
        if c2.button("회원가입", use_container_width=True):
            go_to("register")
    else:
        st.write(f"**{st.session_state.display_name}**님, 준비가 되면 시작해 보세요.")
        if st.button("테스트 시작", type="primary", use_container_width=True):
            go_to("quiz", q_idx=0, answers={}, quiz_done=False)

        if st.session_state.history:
            st.caption(f"지금까지 {len(st.session_state.history)}회 테스트 완료")


# ── 로그인 ──

def page_login():
    st.header("로그인")
    st.caption("인증 방식: `data/users.json` 파일에 저장된 사용자 정보와 대조하여 로그인합니다.")

    with st.form("login"):
        uid = st.text_input("아이디")
        pw = st.text_input("비밀번호", type="password")
        go = st.form_submit_button("로그인", use_container_width=True, type="primary")

        if go:
            if not uid or not pw:
                st.error("아이디와 비밀번호를 모두 입력해주세요.")
            else:
                ok, name = authenticate(uid, pw)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.username = uid
                    st.session_state.display_name = name
                    go_to("home")
                else:
                    st.error("로그인 정보가 맞지 않습니다.")

    with st.expander("테스트 계정"):
        st.markdown("`admin` / `admin123` · `kwon` / `1234` · `guest` / `guest`")

    c1, c2 = st.columns(2)
    if c1.button("← 홈으로", use_container_width=True):
        go_to("home")
    if c2.button("회원가입", use_container_width=True):
        go_to("register")


# ── 회원가입 ──

def page_register():
    st.header("회원가입")

    with st.form("register"):
        uid = st.text_input("아이디 (2자 이상)")
        name = st.text_input("이름")
        pw = st.text_input("비밀번호 (3자 이상)", type="password")
        pw2 = st.text_input("비밀번호 확인", type="password")
        go = st.form_submit_button("가입", use_container_width=True, type="primary")

        if go:
            all_users = {**load_user_data().get("users", {}), **st.session_state.reg_users}
            if not uid or not name or not pw:
                st.error("모든 항목을 입력해주세요.")
            elif len(uid) < 2:
                st.error("아이디가 너무 짧습니다.")
            elif len(pw) < 3:
                st.error("비밀번호가 너무 짧습니다.")
            elif pw != pw2:
                st.error("비밀번호가 일치하지 않습니다.")
            elif uid in all_users:
                st.error("이미 사용 중인 아이디입니다.")
            else:
                st.session_state.reg_users[uid] = {"password": pw, "name": name}
                st.success(f"{name}님, 가입이 완료되었습니다. 로그인해 주세요.")

    if st.button("← 로그인으로", use_container_width=True):
        go_to("login")


# ── 퀴즈 (한 문제씩) ──

def page_quiz():
    if not st.session_state.logged_in:
        st.warning("로그인이 필요합니다.")
        if st.button("로그인하기"):
            go_to("login")
        return

    quiz = load_quiz_data()
    questions = quiz["questions"]
    total = len(questions)
    idx = st.session_state.q_idx

    st.progress(idx / total, text=f"{idx} / {total}")

    st.markdown(
        f'<div class="quiz-status">'
        f"<strong>{st.session_state.display_name}</strong>님 · "
        f"문항 {idx + 1} / {total}"
        f"</div>",
        unsafe_allow_html=True,
    )

    q = questions[idx]
    st.subheader(f"Q{idx + 1}. {q['question']}")

    cur = st.session_state.answers.get(idx, None)
    options = [opt["text"] for opt in q["options"]]
    sel = st.radio("답변 선택", options, index=cur, key=f"q_{idx}", label_visibility="collapsed")

    if sel is not None:
        st.session_state.answers[idx] = options.index(sel)

    st.markdown("---")

    left, mid, right = st.columns([1, 1, 1])
    if idx > 0:
        if left.button("← 이전", use_container_width=True):
            st.session_state.q_idx = idx - 1
            st.rerun()

    answered_cnt = sum(1 for v in st.session_state.answers.values() if v is not None)
    mid.markdown(f"<div style='text-align:center;padding-top:0.4rem'>{answered_cnt}/{total} 응답</div>", unsafe_allow_html=True)

    if idx < total - 1:
        if right.button("다음 →", use_container_width=True, type="primary"):
            if sel is None:
                st.warning("답변을 선택해 주세요.")
            else:
                st.session_state.q_idx = idx + 1
                st.rerun()
    else:
        if right.button("결과 보기", use_container_width=True, type="primary"):
            unanswered = [i + 1 for i in range(total) if st.session_state.answers.get(i) is None]
            if unanswered:
                st.warning(f"아직 답변하지 않은 문항이 있습니다: {', '.join(f'Q{n}' for n in unanswered)}")
            else:
                _submit(questions)

    with st.expander("전체 문항 이동"):
        cols = st.columns(5)
        for i in range(total):
            c = cols[i % 5]
            done = i in st.session_state.answers
            label = f"{'●' if done else '○'} {i+1}"
            if c.button(label, key=f"jmp_{i}", use_container_width=True):
                st.session_state.q_idx = i
                st.rerun()


def _submit(questions):
    total = len(questions)
    tup = tuple(st.session_state.answers.get(i, 0) for i in range(total))
    scores, ranked = compute_scores(tup, total)

    st.session_state.scores = scores
    st.session_state.ranked = ranked
    st.session_state.quiz_done = True

    st.session_state.history.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "scores": scores.copy(),
        "ranked": ranked.copy(),
    })

    go_to("result")


# ── 결과 ──

def page_result():
    if not st.session_state.quiz_done:
        st.warning("테스트를 먼저 진행해주세요.")
        if st.button("테스트 시작"):
            go_to("quiz", q_idx=0, answers={}, quiz_done=False)
        return

    quiz = load_quiz_data()
    rd = quiz["results"]
    scores = st.session_state.scores
    ranked = st.session_state.ranked

    top_score = ranked[0][1]

    # 동점인 직무들을 모두 찾기
    tied = [k for k, v in ranked if v == top_score]

    if len(tied) == 1:
        # 단독 1위
        top = rd[tied[0]]
        st.markdown(
            f'<div class="result-box">'
            f'<div class="big-emoji">{top["emoji"]}</div>'
            f'<h2>{top["title"]}</h2>'
            f"<p>{st.session_state.display_name}님에게 가장 어울리는 직무</p>"
            f'<p><em>{top["subtitle"]}</em></p>'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.write(top["description"])
        primary_key = tied[0]
    else:
        # 동점 처리
        names = " & ".join(rd[k]["emoji"] + " " + rd[k]["title"].split(" (")[0] for k in tied)
        st.markdown(
            f'<div class="result-box">'
            f"<h2>{names}</h2>"
            f"<p>{st.session_state.display_name}님은 여러 직무에 골고루 적성이 있습니다!</p>"
            f"<p>각각 {top_score}점으로 동점입니다.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="tie-notice">'
            "동점인 직무가 있습니다. 아래 상세 점수와 설명을 참고해서 "
            "본인에게 더 맞는 쪽을 생각해 보세요."
            "</div>",
            unsafe_allow_html=True,
        )
        for k in tied:
            with st.expander(f"{rd[k]['emoji']} {rd[k]['title']}"):
                st.write(f"*{rd[k]['subtitle']}*")
                st.write(rd[k]["description"])
        primary_key = tied[0]

    # 2순위 (동점이 아닌 경우)
    if len(tied) == 1:
        runner_up_key = ranked[1][0]
        runner_up = rd[runner_up_key]
        st.markdown(
            f'<div class="sub-result-box">'
            f"2순위: {runner_up['emoji']} {runner_up['title']}"
            f" — <em>{runner_up['subtitle']}</em>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # 차트
    tab_radar, tab_bar = st.tabs(["레이더 차트", "막대 차트"])
    labels = [rd[k]["title"].split(" (")[0] for k in TYPE_KEYS]
    vals = [scores.get(k, 0) for k in TYPE_KEYS]

    with tab_radar:
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=labels + [labels[0]],
            fill="toself",
            fillcolor="rgba(71, 85, 105, 0.15)",
            line=dict(color="#475569", width=2),
            marker=dict(size=7, color="#475569"),
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, max(vals) + 1])),
            showlegend=False,
            margin=dict(l=80, r=80, t=20, b=20),
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_bar:
        bar_colors = ["#64748b", "#475569", "#334155", "#1e293b", "#0f172a"]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=vals,
            marker_color=bar_colors,
            text=vals, textposition="outside",
        ))
        fig.update_layout(
            yaxis=dict(title="점수", range=[0, max(vals) + 2]),
            margin=dict(l=40, r=40, t=20, b=20),
            height=380,
        )
        st.plotly_chart(fig, use_container_width=True)

    # 점수 계산 방식 설명
    with st.expander("이 결과는 어떻게 계산되었나요?"):
        st.markdown(
            "각 문항의 선택지는 5개 직무 중 하나에 대응됩니다. "
            "예를 들어 '데이터를 시각화해서 패턴을 찾아본다'를 선택하면 "
            "**데이터 분석가**에 1점이 부여됩니다.\n\n"
            "10문항을 모두 답변하면 직무별로 점수가 합산되고, "
            "가장 높은 점수를 받은 직무가 1순위 결과로 나타납니다. "
            "동점인 경우 해당 직무들을 함께 표시합니다."
        )

    # 점수 상세
    st.subheader("점수 상세")
    total_pts = sum(vals) or 1
    for k in TYPE_KEYS:
        s = scores.get(k, 0)
        pct = s / total_pts * 100
        name = rd[k]["title"].split(" (")[0]
        st.progress(s / 10, text=f"{rd[k]['emoji']} {name}: {s}점 ({pct:.0f}%)")

    st.markdown("---")

    # 추천 스킬
    primary = rd[primary_key]
    st.subheader(f"{primary['title'].split(' (')[0]}에게 필요한 스킬")
    tags = " ".join(f'<span class="skill-tag">{s}</span>' for s in primary["skills"])
    st.markdown(tags, unsafe_allow_html=True)
    st.markdown("")

    # 학습 로드맵
    st.subheader("학습 로드맵")
    for step in primary["roadmap"].split(" → "):
        st.markdown(f'<div class="step-item">{step}</div>', unsafe_allow_html=True)

    st.markdown("")
    st.markdown("---")

    with st.expander("전체 직무 유형 보기"):
        for k in TYPE_KEYS:
            r = rd[k]
            st.markdown(f"**{r['emoji']} {r['title']}** — *{r['subtitle']}*")
            st.write(r["description"])
            st.write("필요 스킬: " + ", ".join(r["skills"]))
            st.markdown("---")

    stup = tuple(scores.get(k, 0) for k in TYPE_KEYS)
    summary = build_summary_text(stup)
    with st.expander("결과 공유용 텍스트"):
        top_name = primary["title"]
        txt = f"DS 직무 유형 테스트 결과\n\n1순위: {primary['emoji']} {top_name}\n\n{summary}"
        st.code(txt, language=None)

    st.markdown("")
    c1, c2, c3 = st.columns(3)
    if c1.button("다시 테스트", use_container_width=True):
        go_to("quiz", q_idx=0, answers={}, quiz_done=False)
    if c2.button("지난 기록", use_container_width=True):
        go_to("history")
    if c3.button("홈으로", use_container_width=True):
        go_to("home")


# ── 기록 ──

def page_history():
    if not st.session_state.logged_in:
        st.warning("로그인이 필요합니다.")
        if st.button("로그인"):
            go_to("login")
        return

    st.header("테스트 기록")
    st.write(f"**{st.session_state.display_name}**님의 결과 히스토리")
    st.markdown("---")

    history = st.session_state.history
    quiz = load_quiz_data()
    rd = quiz["results"]

    if not history:
        st.info("기록이 없습니다.")
        if st.button("테스트 시작", type="primary", use_container_width=True):
            go_to("quiz", q_idx=0, answers={}, quiz_done=False)
        return

    for i, rec in enumerate(reversed(history)):
        num = len(history) - i
        top_key = rec["ranked"][0][0]
        top = rd[top_key]

        st.markdown(
            f'<div class="history-item">'
            f"<strong>#{num}</strong> · {rec['time']}<br>"
            f"{top['emoji']} <strong>{top['title']}</strong>"
            f" — <em>{top['subtitle']}</em>"
            f"</div>",
            unsafe_allow_html=True,
        )

        with st.expander(f"#{num} 상세 점수"):
            for k in TYPE_KEYS:
                s = rec["scores"].get(k, 0)
                name = rd[k]["title"].split(" (")[0]
                st.progress(s / 10, text=f"{rd[k]['emoji']} {name}: {s}점")

    if len(history) >= 2:
        st.markdown("---")
        st.subheader("회차별 변화")
        fig = go.Figure()
        for k in TYPE_KEYS:
            r = rd[k]
            ys = [rec["scores"].get(k, 0) for rec in history]
            xs = [f"#{i+1}" for i in range(len(history))]
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines+markers",
                name=r["title"].split(" (")[0],
            ))
        fig.update_layout(
            yaxis=dict(title="점수", range=[0, 11]),
            xaxis=dict(title="회차"),
            height=340,
            margin=dict(l=40, r=40, t=20, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.35),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("새 테스트", type="primary", use_container_width=True):
        go_to("quiz", q_idx=0, answers={}, quiz_done=False)
    if c2.button("홈으로", use_container_width=True):
        go_to("home")


# ── 직무 소개 ──

def page_jobs():
    quiz = load_quiz_data()
    rd = quiz["results"]

    st.header("직무 소개")
    st.write("데이터 사이언스 분야의 5가지 직무를 자세히 알아보세요.")
    st.markdown("---")

    job_names = {
        "analyst": f"{rd['analyst']['emoji']} 데이터 분석가",
        "scientist": f"{rd['scientist']['emoji']} 데이터 사이언티스트",
        "ml_engineer": f"{rd['ml_engineer']['emoji']} ML 엔지니어",
        "data_engineer": f"{rd['data_engineer']['emoji']} 데이터 엔지니어",
        "ai_researcher": f"{rd['ai_researcher']['emoji']} AI 리서처",
    }

    selected = st.selectbox(
        "직무를 선택하세요",
        TYPE_KEYS,
        format_func=lambda k: job_names[k],
    )

    r = rd[selected]
    st.markdown("---")

    # 기본 정보
    st.subheader(f"{r['emoji']} {r['title']}")
    st.write(f"*{r['subtitle']}*")
    st.write(r["description"])

    st.markdown("---")

    # 하루 일과
    st.subheader("하루 일과 예시")
    for item in r.get("day_in_life", []):
        time_part, desc_part = item.split(" — ", 1)
        st.markdown(
            f'<div class="step-item"><strong>{time_part}</strong> — {desc_part}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # 실제 사례
    if "real_example" in r:
        st.subheader("현업 사례")
        st.info(r["real_example"])

    st.markdown("---")

    # 장단점
    col_pro, col_con = st.columns(2)
    with col_pro:
        st.subheader("장점")
        for p in r.get("pros", []):
            st.write(f"✓ {p}")
    with col_con:
        st.subheader("단점")
        for c in r.get("cons", []):
            st.write(f"✗ {c}")

    st.markdown("---")

    # 필요 스킬
    st.subheader("필요 스킬")
    tags = " ".join(f'<span class="skill-tag">{s}</span>' for s in r["skills"])
    st.markdown(tags, unsafe_allow_html=True)
    st.markdown("")

    # 학습 로드맵
    st.subheader("학습 로드맵")
    for step in r["roadmap"].split(" → "):
        st.markdown(f'<div class="step-item">{step}</div>', unsafe_allow_html=True)

    st.markdown("")

    # 커리어 패스
    if "career_path" in r:
        st.subheader("커리어 패스")
        stages = r["career_path"].split(" → ")
        path_cols = st.columns(len(stages))
        for i, (col, stage) in enumerate(zip(path_cols, stages)):
            arrow = "" if i == 0 else "→ "
            col.markdown(f"**{arrow}{stage}**")

    st.markdown("---")

    if st.session_state.logged_in:
        if st.button("나에게 맞는 직무 테스트하기", type="primary", use_container_width=True):
            go_to("quiz", q_idx=0, answers={}, quiz_done=False)
    else:
        st.info("테스트를 하려면 먼저 로그인해 주세요.")


# ── 캐싱 시연 ──

def page_cache_demo():
    st.header("캐싱 시연")
    st.caption(
        "이 페이지에서 확인하는 `load_quiz_data()`는 "
        "퀴즈 화면, 결과 화면, 직무 소개 등 앱 전체에서 실제로 사용되는 데이터 로딩 함수입니다."
    )

    st.markdown("---")

    # 현재 캐시된 데이터 정보 표시
    quiz = load_quiz_data()
    json_path = os.path.join(os.path.dirname(__file__), "data", "quiz_data.json")
    file_size = os.path.getsize(json_path)

    st.subheader("캐싱 적용 현황")

    c1, c2, c3 = st.columns(3)
    c1.metric("문항 수", f"{len(quiz['questions'])}개")
    c2.metric("직무 유형", f"{len(quiz['results'])}개")
    c3.metric("파일 크기", f"{file_size / 1024:.1f} KB")

    st.markdown(
        "| 항목 | 값 |\n"
        "|------|----|\n"
        "| 캐싱 적용 함수 | `load_quiz_data()` |\n"
        "| 데코레이터 | `@st.cache_data` |\n"
        "| 대상 파일 | `data/quiz_data.json` |"
    )

    st.markdown("---")

    st.info(
        "이 캐싱은 실제 퀴즈 화면에서 사용하는 `quiz_data.json` 로딩 함수에 적용되어 있습니다. "
        "데이터 파일이 작기 때문에 시간 차이는 크지 않을 수 있지만, "
        "동일한 데이터를 반복해서 읽지 않도록 Streamlit 캐시를 사용합니다."
    )

    st.markdown("---")

    # 실행 시간 비교
    st.subheader("실행 시간 비교")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("캐시된 데이터 접근", type="primary", use_container_width=True):
            start = time.perf_counter()
            load_quiz_data()
            elapsed = time.perf_counter() - start
            st.session_state["_last_cached_ms"] = elapsed * 1000

    with col2:
        if st.button("캐시 초기화 후 다시 로딩", use_container_width=True):
            load_quiz_data.clear()
            start = time.perf_counter()
            load_quiz_data()
            elapsed = time.perf_counter() - start
            st.session_state["_last_cleared_ms"] = elapsed * 1000

    cached_ms = st.session_state.get("_last_cached_ms")
    cleared_ms = st.session_state.get("_last_cleared_ms")

    if cached_ms is not None or cleared_ms is not None:
        st.markdown("")
        m1, m2 = st.columns(2)
        if cached_ms is not None:
            m1.metric("캐시 적용 (메모리)", f"{cached_ms:.4f} ms")
        if cleared_ms is not None:
            m2.metric("캐시 초기화 후 (파일 I/O)", f"{cleared_ms:.4f} ms")

        if cached_ms is not None and cleared_ms is not None and cleared_ms > 0:
            ratio = cleared_ms / max(cached_ms, 0.0001)
            st.caption(f"캐시 적용 시 약 {ratio:.0f}배 빠르게 데이터를 반환했습니다.")

    st.markdown("---")

    st.caption(
        "`@st.cache_data`는 함수의 반환값을 메모리에 저장합니다. "
        "Streamlit은 사용자 조작마다 스크립트 전체를 재실행하기 때문에, "
        "캐싱이 없으면 매번 디스크에서 JSON 파일을 다시 읽게 됩니다. "
        "캐싱을 적용하면 최초 1회만 파일을 읽고, 이후에는 메모리에서 즉시 반환합니다."
    )


# ── 라우팅 ──

sidebar()

p = st.session_state.page
if p == "home":
    page_home()
elif p == "login":
    page_login()
elif p == "register":
    page_register()
elif p == "quiz":
    page_quiz()
elif p == "result":
    page_result()
elif p == "history":
    page_history()
elif p == "jobs":
    page_jobs()
elif p == "cache_demo":
    page_cache_demo()
