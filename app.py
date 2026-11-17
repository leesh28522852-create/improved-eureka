import base64
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
import streamlit as st

st.set_page_config(
    page_title="우리 가족 거리 리그",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="collapsed",
)

LOCAL_DATA = Path(__file__).with_name("family_run_data.json")
REWARDS = ["설거지 면제권", "빨래 면제권", "청소기 면제권"]

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Noto+Sans+KR:wght@400;500;600;700;800;900&display=swap');
    :root { --ink:#18251f; --muted:#718078; --green:#236b4d; --mint:#dff3e8; --lime:#c9ef77; --paper:#f7f8f2; }
    html, body, [class*="css"] { font-family:'DM Sans','Noto Sans KR',sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stHeader"] { background:transparent; }
    .block-container { max-width:1120px; padding-top:1.4rem; padding-bottom:3rem; }
    .hero { background:linear-gradient(120deg,#173d2e 0%,#236b4d 62%,#348b63 100%); color:white; border-radius:28px; padding:30px 34px; position:relative; overflow:hidden; margin-bottom:22px; }
    .hero:after { content:'✳'; position:absolute; right:44px; top:-44px; font-size:210px; line-height:1; color:rgba(255,255,255,.07); transform:rotate(18deg); }
    .eyebrow { font-size:12px; font-weight:800; letter-spacing:2px; text-transform:uppercase; color:#c9ef77; margin-bottom:10px; }
    .hero h1 { font-size:clamp(28px,4vw,42px); line-height:1.16; margin:0 0 10px 0; font-weight:900; letter-spacing:-1.3px; color:#fff; }
    .hero p { margin:0; color:#d9ebe1; font-size:15px; }
    .week-pill { display:inline-block; margin-top:18px; padding:8px 13px; border:1px solid rgba(255,255,255,.23); border-radius:99px; color:#eff8f1; font-size:12px; font-weight:700; background:rgba(255,255,255,.08); }
    .section-title { font-size:21px; font-weight:900; letter-spacing:-.5px; margin:24px 0 12px; color:var(--ink); }
    .subtle { color:var(--muted); font-size:13px; }
    .stat-card { background:#fff; border:1px solid #e8eee8; border-radius:20px; padding:18px 20px; min-height:112px; box-shadow:0 5px 18px rgba(22,55,37,.035); }
    .stat-label { color:#78847b; font-size:12px; font-weight:700; margin-bottom:9px; }
    .stat-value { color:#193d2d; font-size:28px; font-weight:900; letter-spacing:-.8px; }
    .stat-note { color:#849087; font-size:11px; margin-top:3px; }
    .rank-card { background:#fff; border:1px solid #e7eee7; border-radius:18px; padding:15px 18px; margin:9px 0; display:flex; align-items:center; gap:14px; }
    .rank-no { width:38px; height:38px; display:flex; align-items:center; justify-content:center; border-radius:14px; background:#f0f4ef; color:#617068; font-weight:900; }
    .rank-no.first { background:#e7f5bc; color:#4b6515; }
    .rank-name { font-weight:800; font-size:15px; }
    .rank-distance { margin-left:auto; font-size:18px; font-weight:900; color:#236b4d; white-space:nowrap; }
    .progress-track { height:7px; width:100%; background:#eef2ed; border-radius:9px; margin-top:8px; overflow:hidden; }
    .progress-fill { height:100%; background:linear-gradient(90deg,#7fc866,#c9ef77); border-radius:9px; }
    .reward-box { background:linear-gradient(135deg,#fff6d8,#fffdf5); border:1px solid #f1e2aa; border-radius:22px; padding:20px 22px; }
    .reward-ticket { background:#fff; border:1px dashed #d6b955; color:#604f1a; border-radius:16px; padding:15px 18px; font-size:20px; font-weight:900; display:inline-block; margin-top:10px; }
    div.stButton > button { border-radius:13px; border:0; font-weight:800; min-height:44px; }
    div.stButton > button[kind="primary"] { background:#236b4d; color:white; }
    div.stButton > button[kind="primary"]:hover { background:#174c35; color:white; }
    div[data-testid="stForm"] { background:#fff; border:1px solid #e8eee8; border-radius:20px; padding:20px; }
    .footer-note { color:#8a958d; font-size:11px; text-align:center; margin-top:28px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def default_data():
    return {"members": ["나", "가족 1", "가족 2"], "activities": [], "rewards": {}}


def github_configured():
    try:
        return bool(st.secrets.get("GITHUB_TOKEN") and st.secrets.get("GITHUB_REPO"))
    except Exception:
        return False


def github_settings():
    return {
        "token": st.secrets["GITHUB_TOKEN"],
        "repo": st.secrets["GITHUB_REPO"],
        "branch": st.secrets.get("GITHUB_BRANCH", "main"),
        "path": st.secrets.get("GITHUB_DATA_PATH", "family_run_data.json"),
    }


def load_data():
    if github_configured():
        cfg = github_settings()
        url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
        headers = {"Authorization": f"Bearer {cfg['token']}", "Accept": "application/vnd.github+json"}
        try:
            response = requests.get(url, headers=headers, params={"ref": cfg["branch"]}, timeout=15)
            if response.status_code == 404:
                return default_data(), None, "github"
            response.raise_for_status()
            payload = response.json()
            raw = base64.b64decode(payload["content"]).decode("utf-8")
            data = json.loads(raw)
            data.setdefault("members", [])
            data.setdefault("activities", [])
            data.setdefault("rewards", {})
            return data, payload.get("sha"), "github"
        except Exception as exc:
            st.error(f"공유 데이터를 불러오지 못했어요: {exc}")
            st.stop()
    if LOCAL_DATA.exists():
        try:
            return json.loads(LOCAL_DATA.read_text(encoding="utf-8")), None, "local"
        except Exception:
            return default_data(), None, "local"
    return default_data(), None, "local"


def save_data(data, sha, storage):
    body = json.dumps(data, ensure_ascii=False, indent=2)
    if storage == "github":
        cfg = github_settings()
        url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
        headers = {"Authorization": f"Bearer {cfg['token']}", "Accept": "application/vnd.github+json"}
        payload = {"message": "Update family distance league data", "content": base64.b64encode(body.encode("utf-8")).decode("ascii"), "branch": cfg["branch"]}
        if sha:
            payload["sha"] = sha
        response = requests.put(url, headers=headers, json=payload, timeout=20)
        if response.status_code in (409, 422):
            raise RuntimeError("가족이 동시에 기록을 저장했어요. 페이지를 새로고침한 뒤 다시 시도해 주세요.")
        response.raise_for_status()
        return response.json().get("content", {}).get("sha")
    LOCAL_DATA.write_text(body, encoding="utf-8")
    return None


def week_start(day):
    return day - timedelta(days=day.weekday())


def current_week_key():
    return week_start(date.today()).isoformat()


def this_week_activities(data):
    start = week_start(date.today()).isoformat()
    end = (date.fromisoformat(start) + timedelta(days=7)).isoformat()
    return [a for a in data["activities"] if start <= a.get("date", "") < end]


def totals_by_member(data, activities=None):
    activities = data["activities"] if activities is None else activities
    totals = {name: 0.0 for name in data["members"]}
    for item in activities:
        if item.get("member") in totals:
            totals[item["member"]] += float(item.get("distance", 0))
    return totals


def persist(updated_data, current_sha, storage):
    try:
        return save_data(updated_data, current_sha, storage), None
    except Exception as exc:
        return current_sha, str(exc)


data, data_sha, storage = load_data()
data["members"] = list(dict.fromkeys([m.strip() for m in data.get("members", []) if m.strip()]))
if not data["members"]:
    data["members"] = ["나"]

now = date.today()
week_start_day = week_start(now)
week_end_day = week_start_day + timedelta(days=6)
week_label = f"{week_start_day.strftime('%m.%d')} — {week_end_day.strftime('%m.%d')}"
weekly = this_week_activities(data)
weekly_totals = totals_by_member(data, weekly)
all_totals = totals_by_member(data)
ranked = sorted(weekly_totals.items(), key=lambda item: (-item[1], item[0]))
leader = ranked[0] if ranked and ranked[0][1] > 0 else None

st.markdown(
    f"""
    <div class="hero">
      <div class="eyebrow">FAMILY MOVE CLUB · WEEKLY CHALLENGE</div>
      <h1>우리 가족, 이번 주<br>누가 가장 멀리 갈까요?</h1>
      <p>걷고 뛰며 쌓은 거리를 함께 기록하고, 이번 주 챔피언을 뽑아봐요.</p>
      <span class="week-pill">📅 이번 주 {week_label}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
week_total = sum(weekly_totals.values())
week_sessions = len(weekly)
leader_name = leader[0] if leader else "아직 기록 없음"
for col, label, value, note in [
    (col1, "이번 주 가족 총 거리", f"{week_total:.1f} km", "이번 주 모두가 함께 달린 거리"),
    (col2, "이번 주 활동 기록", f"{week_sessions}회", "걷기와 달리기 기록 수"),
    (col3, "현재 1위", leader_name, f"{leader[1]:.1f} km" if leader else "첫 기록의 주인공이 되어보세요"),
]:
    with col:
        st.markdown(f'<div class="stat-card"><div class="stat-label">{label}</div><div class="stat-value">{value}</div><div class="stat-note">{note}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">🏆 이번 주 가족 순위</div>', unsafe_allow_html=True)
st.markdown('<div class="subtle">월요일부터 일요일까지 기록한 거리로 집계돼요.</div>', unsafe_allow_html=True)
max_distance = max([v for _, v in ranked], default=0)
if max_distance <= 0:
    st.info("아직 이번 주 기록이 없어요. 첫 산책이나 러닝을 기록해 보세요!")
else:
    for idx, (name, distance) in enumerate(ranked, start=1):
        medal = "🥇" if idx == 1 and distance > 0 else ("🥈" if idx == 2 and distance > 0 else ("🥉" if idx == 3 and distance > 0 else str(idx)))
        width = max(5, int(distance / max_distance * 100)) if distance else 0
        rank_class = "first" if idx == 1 and distance > 0 else ""
        st.markdown(
            f'<div class="rank-card"><div class="rank-no {rank_class}">{medal}</div><div style="flex:1"><div class="rank-name">{name}</div><div class="progress-track"><div class="progress-fill" style="width:{width}%"></div></div></div><div class="rank-distance">{distance:.1f} <span style="font-size:12px;color:#849087">km</span></div></div>',
            unsafe_allow_html=True,
        )

st.markdown('<div class="section-title">🎟️ 이번 주 집안일 면제권</div>', unsafe_allow_html=True)
reward = data["rewards"].get(current_week_key())
with st.container():
    st.markdown('<div class="reward-box"><b>주간 우승 보상</b><div class="subtle" style="margin-top:5px">1등에게 설거지 · 빨래 · 청소기 중 랜덤 면제권 한 장!</div></div>', unsafe_allow_html=True)
if reward:
    st.markdown(f'<div class="reward-ticket">🎉 {reward["member"]} · {reward["prize"]}</div>', unsafe_allow_html=True)
    st.caption("이번 주 면제권은 이미 뽑혔어요. 다음 주에 다시 도전해요!")
elif leader:
    if st.button("이번 주 1등 면제권 뽑기", type="primary", use_container_width=False):
        current_leader_distance = max(weekly_totals.values(), default=0)
        winners = [name for name, value in weekly_totals.items() if value == current_leader_distance and value > 0]
        if winners:
            winner_name = random.choice(winners)
            updated = json.loads(json.dumps(data, ensure_ascii=False))
            updated["rewards"][current_week_key()] = {"member": winner_name, "prize": random.choice(REWARDS), "drawn_at": datetime.now().isoformat(timespec="seconds")}
            new_sha, error = persist(updated, data_sha, storage)
            if error:
                st.error(f"면제권 저장 실패: {error}")
            else:
                st.success("이번 주 면제권을 뽑았어요!")
                st.rerun()
else:
    st.caption("이번 주 거리를 기록하면 1등 면제권을 뽑을 수 있어요.")

st.markdown('<div class="section-title">➕ 오늘의 거리 기록</div>', unsafe_allow_html=True)
with st.form("activity_form", clear_on_submit=True):
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
    member = c1.selectbox("가족 구성원", data["members"])
    activity_type = c2.selectbox("활동", ["걷기", "달리기"])
    distance = c3.number_input("거리 (km)", min_value=0.1, max_value=200.0, value=2.0, step=0.1)
    activity_date = c4.date_input("날짜", value=now)
    submitted = st.form_submit_button("거리 기록하기", type="primary", use_container_width=True)
if submitted:
    updated = json.loads(json.dumps(data, ensure_ascii=False))
    updated["activities"].append({"id": datetime.now().strftime("%Y%m%d%H%M%S%f"), "member": member, "type": activity_type, "distance": round(float(distance), 2), "date": activity_date.isoformat()})
    new_sha, error = persist(updated, data_sha, storage)
    if error:
        st.error(f"기록 저장 실패: {error}")
    else:
        st.success(f"{member}님의 {activity_type} {distance:.1f}km를 기록했어요!")
        st.rerun()

with st.expander("가족 구성원 추가"):
    with st.form("member_form", clear_on_submit=True):
        new_member = st.text_input("이름 또는 별명", max_chars=24, placeholder="예: 엄마, 민수")
        add_member = st.form_submit_button("가족 추가")
    if add_member:
        clean_name = new_member.strip()
        if not clean_name:
            st.warning("이름을 입력해 주세요.")
        elif clean_name in data["members"]:
            st.warning("이미 등록된 이름이에요.")
        else:
            updated = json.loads(json.dumps(data, ensure_ascii=False))
            updated["members"].append(clean_name)
            new_sha, error = persist(updated, data_sha, storage)
            if error:
                st.error(f"가족 추가 실패: {error}")
            else:
                st.success(f"{clean_name}님을 가족 리그에 추가했어요!")
                st.rerun()

st.markdown('<div class="section-title">📒 최근 활동</div>', unsafe_allow_html=True)
recent = sorted(data["activities"], key=lambda a: (a.get("date", ""), a.get("id", "")), reverse=True)[:10]
if not recent:
    st.caption("아직 활동 기록이 없어요.")
else:
    for item in recent:
        icon = "🚶" if item.get("type") == "걷기" else "🏃"
        st.markdown(f"**{icon} {item.get('member', '가족')}** · {item.get('type', '활동')} · **{float(item.get('distance', 0)):.1f} km**  <span style='color:#89958d'>· {item.get('date', '')}</span>", unsafe_allow_html=True)

st.markdown('<div class="section-title">🌱 우리 가족 누적 거리</div>', unsafe_allow_html=True)
with st.expander("가족별 누적 기록 보기"):
    for name, distance in sorted(all_totals.items(), key=lambda x: (-x[1], x[0])):
        st.write(f"**{name}**　{distance:.1f} km")

if storage == "github":
    st.markdown('<div class="footer-note">가족 데이터는 연결된 비공개 GitHub 저장소에 저장됩니다.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="footer-note">로컬 미리보기 모드 · 가족이 함께 쓰려면 Streamlit Secrets에 GitHub 저장소를 연결하세요.</div>', unsafe_allow_html=True)
