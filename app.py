import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "lottery_app.db"

st.set_page_config(page_title="행운 추첨기", page_icon="🎱", layout="wide", initial_sidebar_state="expanded")


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS participants (
            id TEXT PRIMARY KEY,
            number TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS draw_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drawn_at TEXT NOT NULL,
            winner_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS winners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL REFERENCES draw_rounds(id) ON DELETE CASCADE,
            participant_id TEXT NOT NULL,
            number TEXT NOT NULL,
            name TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_winners_participant ON winners(participant_id);
        """)


def get_participants():
    with db_connection() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM participants ORDER BY created_at, number, name")]


def add_participant(number, name):
    number, name = str(number).strip(), str(name).strip()
    if not name:
        return False, "이름을 입력해 주세요."
    with get_db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM participants WHERE lower(name)=lower(?) AND number=?", (name, number)
        ).fetchone()
        if exists:
            return False, "같은 번호와 이름의 참가자가 이미 있어요."
        conn.execute(
            "INSERT INTO participants(id, number, name, created_at) VALUES(?,?,?,?)",
            (str(uuid.uuid4()), number, name, datetime.now().isoformat(timespec="seconds")),
        )
    return True, f"{name} 참가자를 추가했어요."


def remove_participant(participant_id):
    with get_db() as conn:
        conn.execute("DELETE FROM participants WHERE id=?", (participant_id,))


def clear_participants():
    with get_db() as conn:
        conn.execute("DELETE FROM participants")


def draw_winners(winners):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO draw_rounds(drawn_at, winner_count) VALUES(?,?)", (now, len(winners))
        )
        round_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO winners(round_id, participant_id, number, name) VALUES(?,?,?,?)",
            [(round_id, p["id"], p["number"], p["name"]) for p in winners],
        )
    return round_id, now


def get_history():
    with get_db() as conn:
        rounds = [dict(r) for r in conn.execute("SELECT * FROM draw_rounds ORDER BY id DESC")]
        for r in rounds:
            r["winners"] = [dict(w) for w in conn.execute(
                "SELECT number, name, participant_id FROM winners WHERE round_id=? ORDER BY id", (r["id"],)
            )]
    return rounds


def clear_history():
    with get_db() as conn:
        conn.execute("DELETE FROM draw_rounds")


def parse_bulk(text):
    parsed = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "," in line:
            number, name = line.split(",", 1)
        elif "\t" in line:
            number, name = line.split("\t", 1)
        else:
            number, name = "", line
        name, number = name.strip(), number.strip()
        if name.lower() in {"이름", "name"} and number.lower() in {"번호", "number", "no"}:
            continue
        parsed.append((number, name))
    return parsed


def number_for_new(index):
    return f"{index:03d}"


def safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def draw_animation(round_id, winners):
    payload = safe_json([{"number": p["number"], "name": p["name"]} for p in winners])
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#101522;color:#f8fafc;font-family:Inter,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif}}
.scene{{height:438px;position:relative;overflow:hidden;border:1px solid #273149;border-radius:24px;background:radial-gradient(ellipse at 50% 5%,#293858 0,#151c2c 54%,#101522 100%);display:flex;flex-direction:column;align-items:center;padding:20px 16px}}
.eyebrow{{font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:#9aa9c8;font-weight:800}} h2{{margin:5px 0 8px;font-size:22px;letter-spacing:-.04em}}
.sub{{color:#aab4c9;font-size:13px}}
.machine{{width:320px;height:198px;position:relative;margin-top:18px;perspective:900px}}
.glass{{position:absolute;inset:4px 12px 18px;border:3px solid rgba(211,226,255,.75);border-radius:50%;background:linear-gradient(145deg,rgba(255,255,255,.14),rgba(88,139,216,.06) 48%,rgba(255,255,255,.12));box-shadow:inset 0 0 28px rgba(188,217,255,.18),0 0 30px rgba(71,136,255,.18);overflow:hidden}}
.glass:before{{content:"";position:absolute;left:12%;top:7%;width:45%;height:22%;border-radius:50%;background:rgba(255,255,255,.25);filter:blur(7px);transform:rotate(-17deg);z-index:4}}
.drum{{position:absolute;inset:0;transform-style:preserve-3d;animation:spin .72s linear infinite}}
.ball{{position:absolute;width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:10px;color:#24283a;border:1px solid rgba(255,255,255,.75);box-shadow:inset -4px -5px 7px rgba(0,0,0,.2),inset 4px 4px 8px rgba(255,255,255,.8),0 4px 8px rgba(0,0,0,.25);animation:bob .38s ease-in-out infinite alternate}}
@keyframes spin{{0%{{transform:rotateX(0) rotateY(0) rotateZ(0)}}100%{{transform:rotateX(360deg) rotateY(360deg) rotateZ(360deg)}}}}
@keyframes bob{{from{{translate:0 -5px}}to{{translate:0 7px}}}}
.base{{position:absolute;left:50%;bottom:4px;width:212px;height:18px;transform:translateX(-50%);border-radius:50%;background:linear-gradient(90deg,#65728b,#e3ecff,#65728b);box-shadow:0 8px 20px rgba(0,0,0,.45)}}
.status{{height:25px;margin-top:0;font-size:13px;color:#c6d2e9;font-weight:700}}
.results{{display:flex;gap:9px;justify-content:center;flex-wrap:wrap;max-width:100%;margin-top:5px}}
.ticket{{min-width:112px;padding:9px 12px;text-align:center;border-radius:15px;background:linear-gradient(140deg,#ffe77a,#ffbd56);color:#3a2c12;box-shadow:0 8px 24px rgba(255,194,66,.25);opacity:0;transform:translateY(35px) scale(.72) rotate(-8deg)}}
.ticket.show{{animation:pop .55s cubic-bezier(.16,1.4,.45,1) forwards}}
.ticket small{{display:block;font-size:10px;font-weight:900;opacity:.72;letter-spacing:.08em}} .ticket strong{{display:block;font-size:17px;margin-top:2px;overflow-wrap:anywhere}}
@keyframes pop{{to{{opacity:1;transform:translateY(0) scale(1) rotate(0)}}}}
.spark{{position:absolute;width:6px;height:6px;border-radius:50%;background:#ffe77a;box-shadow:0 0 13px #ffe77a;animation:twinkle 1.1s ease-in-out infinite alternate}}
@keyframes twinkle{{to{{opacity:.18;transform:scale(.5)}}}}
@media(max-width:500px){{.machine{{transform:scale(.86);margin-top:5px;margin-bottom:-10px}}.scene{{height:420px}} h2{{font-size:19px}}}}
</style></head><body><div class="scene" data-round="{round_id}">
<div class="eyebrow">LUCKY DRAW · ROUND {round_id}</div><h2>행운의 주인공을 뽑고 있어요</h2><div class="sub">공들이 추첨통 안에서 섞이고 있어요…</div>
<div class="machine"><div class="glass"><div class="drum" id="drum"></div></div><div class="base"></div></div>
<div class="status" id="status">추첨통을 돌리는 중</div><div class="results" id="results"></div>
</div><script>
const winners={payload}; const colors=['#ff8c70','#7cceff','#ffe176','#b79cff','#91e5ae','#ffb6d5','#f6a65e'];
const drum=document.getElementById('drum');
for(let i=0;i<24;i++){{const b=document.createElement('div');b.className='ball';b.style.left=(5+Math.random()*84)+'%';b.style.top=(12+Math.random()*68)+'%';b.style.background=colors[i%colors.length];b.style.animationDelay=(Math.random()*.4)+'s';b.textContent=String(1+Math.floor(Math.random()*99));drum.appendChild(b)}}
for(let i=0;i<9;i++){{const s=document.createElement('i');s.className='spark';s.style.left=(8+Math.random()*84)+'%';s.style.top=(15+Math.random()*70)+'%';s.style.animationDelay=(Math.random()*.8)+'s';document.querySelector('.scene').appendChild(s)}}
setTimeout(()=>{{drum.style.animation='none';document.getElementById('status').textContent='당첨 공이 나왔어요!';document.querySelector('.sub').textContent='축하합니다! 오늘의 행운을 확인하세요';winners.forEach((w,i)=>setTimeout(()=>{{const t=document.createElement('div');t.className='ticket';const n=document.createElement('small');n.textContent=w.number?('NO. '+w.number):'당첨자';const name=document.createElement('strong');name.textContent=w.name;t.append(n,name);document.getElementById('results').appendChild(t);requestAnimationFrame(()=>t.classList.add('show'))}},i*650))}},2400);
</script></body></html>'''
    components.html(html, height=450, scrolling=False)


def render_participant_table(people, show_delete=False):
    if not people:
        st.info("아직 참가자가 없어요. 아래에서 참가자를 추가해 주세요.")
        return
    header = st.columns([1, 4, 1] if show_delete else [1, 5])
    header[0].markdown("**번호**")
    header[1].markdown("**이름**")
    if show_delete:
        header[2].markdown("**삭제**")
    for p in people:
        cols = st.columns([1, 4, 1] if show_delete else [1, 5])
        cols[0].write(p["number"] or "—")
        cols[1].write(p["name"])
        if show_delete and cols[2].button("삭제", key=f"del_{p['id']}"):
            remove_participant(p["id"])
            st.rerun()


init_db()
if "last_round_id" not in st.session_state:
    st.session_state.last_round_id = None
if "show_animation" not in st.session_state:
    st.session_state.show_animation = False

st.markdown("""
<style>
:root{--ink:#172033;--muted:#718096;--purple:#6c5ce7}
.stApp{background:linear-gradient(180deg,#f6f7ff 0,#f8fafc 280px,#f8fafc 100%)}
.block-container{padding-top:2rem;padding-bottom:3rem;max-width:1120px}
[data-testid="stSidebar"]{background:#111827}
[data-testid="stSidebar"] *{color:#edf1fb}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:8px 10px;border-radius:10px}
.card{background:#fff;border:1px solid #e8eaf2;border-radius:18px;padding:20px 22px;box-shadow:0 8px 28px rgba(38,48,82,.045)}
.hero{padding:8px 0 16px}.hero h1{font-size:34px;letter-spacing:-.055em;margin:0;color:#182238}.hero p{color:#707b91;margin:6px 0 0}
.small-muted{color:#778197;font-size:13px}
div.stButton>button{border-radius:11px;font-weight:700;min-height:42px}
div.stButton>button[kind="primary"]{background:#6c5ce7;border-color:#6c5ce7}
hr{border-color:#e7eaf1}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("# 🎱 행운 추첨기")
    st.caption("가볍고 즐거운 랜덤 추첨")
    page = st.radio("메뉴", ["🎉 추첨하기", "👥 참가자 관리", "🏆 추첨 결과"], label_visibility="collapsed")
    st.markdown("---")
    people_count = len(get_participants())
    st.caption(f"등록 참가자  **{people_count}명**")
    st.caption("데이터는 이 앱의 SQLite 파일에 저장됩니다.")

people = get_participants()
history = get_history()

if page == "🎉 추첨하기":
    st.markdown('<div class="hero"><h1>오늘의 행운을 뽑아볼까요?</h1><p>추첨통을 돌리고, 행운의 주인공을 확인해 보세요.</p></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### 🎟️ 추첨 설정")
        st.write(f"참가자 **{len(people)}명**")
        count = st.number_input("당첨 인원", min_value=1, max_value=max(1, len(people)), value=1, step=1, disabled=not people)
        exclude_previous = st.checkbox("이전 회차 당첨자 제외", value=True, help="체크하면 이전 추첨 당첨자는 다음 추첨 후보에서 제외됩니다.")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### 📋 참가자 미리보기")
        if people:
            st.write(" · ".join([f"{p['number'] + '번 ' if p['number'] else ''}{p['name']}" for p in people[:6]]) + (f" 외 {len(people)-6}명" if len(people)>6 else ""))
        else:
            st.write("참가자를 먼저 등록해 주세요.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    if not people:
        st.warning("참가자 관리 메뉴에서 참가자를 등록하면 바로 추첨할 수 있어요.")
    elif st.session_state.show_animation:
        last = next((r for r in history if r["id"] == st.session_state.last_round_id), None)
        if last:
            draw_animation(last["id"], last["winners"])
            st.success(f"{last['id']}회 추첨 결과가 저장됐어요.")
            st.markdown("#### 🥳 당첨자")
            result_cols = st.columns(min(4, len(last["winners"])))
            for i, winner in enumerate(last["winners"]):
                with result_cols[i % len(result_cols)]:
                    st.markdown(f"<div class='card'><div class='small-muted'>{winner['number'] or '당첨'}</div><div style='font-size:22px;font-weight:800'>{winner['name']}</div></div>", unsafe_allow_html=True)
            if st.button("🔄 다시 추첨하기", type="primary"):
                st.session_state.show_animation = False
                st.rerun()
        else:
            st.session_state.show_animation = False
            st.rerun()
    else:
        if st.button("🎱 추첨 시작", type="primary", use_container_width=True):
            already_won = set()
            if exclude_previous:
                for r in history:
                    already_won.update(w["participant_id"] for w in r["winners"])
            pool = [p for p in people if p["id"] not in already_won]
            if int(count) > len(pool):
                st.error(f"추첨 가능한 참가자가 {len(pool)}명뿐이에요. 당첨 인원이나 이전 당첨자 제외 설정을 확인해 주세요.")
            else:
                import random
                selected = random.SystemRandom().sample(pool, int(count))
                round_id, _ = draw_winners(selected)
                st.session_state.last_round_id = round_id
                st.session_state.show_animation = True
                st.rerun()

elif page == "👥 참가자 관리":
    st.markdown('<div class="hero"><h1>참가자 관리</h1><p>한 명씩 추가하거나 여러 명을 한 번에 붙여넣을 수 있어요.</p></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["한 명씩 추가", "여러 명 붙여넣기"])
    with tab1:
        with st.form("single_add", clear_on_submit=True):
            a, b = st.columns([1, 2])
            number = a.text_input("번호 (선택)", placeholder="예: 01")
            name = b.text_input("이름", placeholder="예: 김행운")
            submitted = st.form_submit_button("참가자 추가", type="primary")
            if submitted:
                ok, message = add_participant(number, name)
                (st.success if ok else st.warning)(message)
                if ok:
                    st.rerun()
    with tab2:
        st.markdown("번호와 이름은 `번호, 이름` 형식으로 한 줄씩 입력하세요. 이름만 입력하면 번호는 자동으로 부여됩니다.")
        bulk = st.text_area("참가자 목록", height=180, placeholder="001, 김하늘\n002, 이바다\n박별")
        if st.button("목록 추가", type="primary", disabled=not bulk.strip()):
            rows = parse_bulk(bulk)
            added, skipped = 0, []
            current = get_participants()
            next_number = len(current) + 1
            for number, name in rows:
                if not name:
                    skipped.append("이름이 없는 행")
                    continue
                if not number:
                    number = number_for_new(next_number)
                    next_number += 1
                ok, message = add_participant(number, name)
                if ok:
                    added += 1
                else:
                    skipped.append(f"{number}, {name}")
            if added:
                st.success(f"{added}명을 추가했어요.")
            if skipped:
                st.warning(f"중복 또는 오류로 건너뛴 항목: {', '.join(skipped[:8])}" + (" …" if len(skipped)>8 else ""))
            st.rerun()
    st.markdown("---")
    st.markdown(f"#### 등록 참가자 ({len(people)}명)")
    render_participant_table(people, show_delete=True)
    if people:
        with st.expander("참가자 전체 삭제"):
            st.warning("참가자 목록만 삭제합니다. 이미 저장된 추첨 결과는 유지돼요.")
            if st.button("참가자 전체 삭제", key="clear_people"):
                clear_participants()
                st.rerun()

else:
    st.markdown('<div class="hero"><h1>추첨 결과</h1><p>회차별 당첨자와 추첨 시간을 확인할 수 있어요.</p></div>', unsafe_allow_html=True)
    if not history:
        st.info("아직 추첨 결과가 없어요. 추첨을 진행하면 이곳에 기록됩니다.")
    else:
        st.markdown(f"#### 총 {len(history)}회 추첨")
        for r in history:
            try:
                drawn = datetime.fromisoformat(r["drawn_at"]).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                drawn = r["drawn_at"]
            with st.expander(f"🏆 {r['id']}회 추첨 · {drawn} · 당첨 {r['winner_count']}명", expanded=(r["id"] == history[0]["id"])):
                st.markdown("**당첨자**")
                st.write("　 ·　".join([f"{w['number'] + '번 ' if w['number'] else ''}{w['name']}" for w in r["winners"]]))
        with st.expander("추첨 결과 전체 초기화"):
            st.warning("모든 회차와 당첨자 기록이 삭제됩니다. 참가자 목록은 유지됩니다.")
            confirm = st.checkbox("전체 결과를 삭제하겠습니다.", key="confirm_clear_history")
            if st.button("결과 기록 삭제", disabled=not confirm):
                clear_history()
                st.session_state.show_animation = False
                st.session_state.last_round_id = None
                st.rerun()
