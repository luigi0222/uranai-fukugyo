#!/usr/bin/env python3
"""
占い副業 Web アプリ
受付フォーム → Stripe 決済 → 鑑定書自動生成 → メール納品
"""

import os
import sys
import threading
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import stripe
import json
from flask import Flask, redirect, render_template, request

# ── 設定 ──────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
SYSTEM_PROMPT       = (BASE_DIR.parent / "system_prompt.md").read_text(encoding="utf-8")
SYSTEM_PROMPT_FREE  = (BASE_DIR.parent / "system_prompt_free.md").read_text(encoding="utf-8")
TAROT_SYSTEM_PROMPT = (BASE_DIR.parent / "tarot_system_prompt_love.md").read_text(encoding="utf-8")
TAROT_DATA          = json.loads((BASE_DIR / "tarot_data.json").read_text(encoding="utf-8"))

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

PLANS = {
    "standard": {"name": "スタンダード鑑定（10,000文字）", "amount": 4980},
    "premium":  {"name": "プレミアム鑑定（PDF仕上げ）",   "amount": 9800},
}

# 二重生成防止（プロセス内キャッシュ）
_processed_sessions: set[str] = set()

app = Flask(__name__)

# ── 占術ロジック ──────────────────────────────────────────────────

def get_zodiac_sign(d: date) -> str:
    m, day = d.month, d.day
    if   (m == 3 and day >= 21) or (m == 4  and day <= 19): return "牡羊座 ♈"
    elif (m == 4 and day >= 20) or (m == 5  and day <= 20): return "牡牛座 ♉"
    elif (m == 5 and day >= 21) or (m == 6  and day <= 20): return "双子座 ♊"
    elif (m == 6 and day >= 21) or (m == 7  and day <= 22): return "蟹座 ♋"
    elif (m == 7 and day >= 23) or (m == 8  and day <= 22): return "獅子座 ♌"
    elif (m == 8 and day >= 23) or (m == 9  and day <= 22): return "乙女座 ♍"
    elif (m == 9 and day >= 23) or (m == 10 and day <= 22): return "天秤座 ♎"
    elif (m == 10 and day >= 23) or (m == 11 and day <= 21): return "蠍座 ♏"
    elif (m == 11 and day >= 22) or (m == 12 and day <= 21): return "射手座 ♐"
    elif (m == 12 and day >= 22) or (m == 1  and day <= 19): return "山羊座 ♑"
    elif (m == 1 and day >= 20) or (m == 2  and day <= 18): return "水瓶座 ♒"
    else: return "魚座 ♓"

def get_life_path_number(d: date) -> int:
    total = sum(int(c) for c in d.strftime("%Y%m%d"))
    while total > 9 and total not in (11, 22, 33):
        total = sum(int(c) for c in str(total))
    return total

# ── 鑑定書生成 ────────────────────────────────────────────────────

def generate_fortune_text(birth_date: date, gender: str, concern: str) -> str:
    client = anthropic.Anthropic()
    zodiac = get_zodiac_sign(birth_date)
    life_path = get_life_path_number(birth_date)

    user_message = f"""
以下の情報をもとに、第一章から第六章まで10,000文字以上の本格鑑定書を作成してください。

【生年月日】{birth_date.strftime('%Y年%m月%d日')}
【太陽星座】{zodiac}
【ライフパスナンバー】{life_path}
【性別】{gender}
【お悩み】
{concern}
""".strip()

    result = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=16000,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    return result.content[0].text

# ── メール送信 ────────────────────────────────────────────────────

def build_html_email(content: str, birth_date: date, zodiac: str, life_path: int) -> str:
    body_html = ""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("【") and "章】" in stripped:
            body_html += f'<h2 style="color:#c9a84c;margin-top:36px;border-left:3px solid #9b59b6;padding-left:12px;font-size:1.1em;">{stripped}</h2>\n'
        elif stripped:
            body_html += f'<p style="margin:0 0 1em 0;">{stripped}</p>\n'

    return f"""
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0d0020;font-family:'Hiragino Mincho ProN','Yu Mincho',Georgia,serif;">
  <div style="max-width:680px;margin:0 auto;padding:40px 20px;">

    <div style="text-align:center;margin-bottom:36px;padding-bottom:28px;border-bottom:1px solid rgba(200,150,255,0.25);">
      <div style="font-size:1.8em;color:#c9a84c;letter-spacing:0.3em;margin-bottom:12px;">✦ ✦ ✦</div>
      <h1 style="color:#c9a84c;font-size:1.6em;font-weight:normal;letter-spacing:0.15em;margin:0 0 12px;">
        星詠み 完全鑑定書
      </h1>
      <p style="color:#b090d0;font-size:0.9em;line-height:1.8;margin:0;">
        {birth_date.strftime('%Y年%m月%d日')}生 &nbsp;|&nbsp; {zodiac} &nbsp;|&nbsp; ライフパス {life_path}<br>
        鑑定日：{date.today().strftime('%Y年%m月%d日')}
      </p>
    </div>

    <div style="color:#f0e4ff;line-height:2.1;font-size:1.02em;">
      {body_html}
    </div>

    <div style="text-align:center;margin-top:48px;padding-top:24px;border-top:1px solid rgba(200,150,255,0.25);
                color:#b090d0;font-size:0.88em;line-height:2.0;">
      ✦ この鑑定書はあなただけのために紡がれた言葉です ✦<br>
      星詠み師 月詠（つきよみ）
    </div>

  </div>
</body>
</html>
"""

def send_fortune_email(to_email: str, html_body: str):
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    from_email = os.environ.get("FROM_EMAIL", smtp_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "✨【星詠み 完全鑑定書】が届きました"
    msg["From"] = f"星詠み師 月詠 <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, to_email, msg.as_string())

def generate_and_send(birth_date_str: str, gender: str, concern: str, to_email: str):
    try:
        birth_date = date.fromisoformat(birth_date_str)
        content    = generate_fortune_text(birth_date, gender, concern)
        zodiac     = get_zodiac_sign(birth_date)
        life_path  = get_life_path_number(birth_date)
        html_body  = build_html_email(content, birth_date, zodiac, life_path)
        send_fortune_email(to_email, html_body)
        print(f"[OK] 鑑定書送信完了 → {to_email}", flush=True)
    except Exception as e:
        print(f"[ERROR] generate_and_send: {e}", file=sys.stderr, flush=True)

# ── Flask ルーティング ────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html",
                           stripe_public_key=os.environ.get("STRIPE_PUBLISHABLE_KEY", os.environ.get("STRIPE_PUBLIC_KEY", "")))

@app.route("/order", methods=["POST"])
def create_checkout():
    plan_key = request.form.get("plan", "standard")
    plan = PLANS.get(plan_key, PLANS["standard"])

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "jpy",
                "product_data": {
                    "name": plan["name"],
                    "description": "西洋占星術×タロット 本格鑑定書（生成後メールで納品）",
                },
                "unit_amount": plan["amount"],
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=request.host_url + "success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.host_url,
        customer_email=request.form.get("email"),
        metadata={
            "birth_date": request.form.get("birth_date", ""),
            "gender":     request.form.get("gender", ""),
            "concern":    request.form.get("concern", ""),
            "email":      request.form.get("email", ""),
        },
    )
    return redirect(session.url, 303)

@app.route("/success")
def success():
    session_id = request.args.get("session_id", "")
    if session_id and session_id not in _processed_sessions:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                _processed_sessions.add(session_id)
                meta = session.metadata
                thread = threading.Thread(
                    target=generate_and_send,
                    args=(meta["birth_date"], meta["gender"], meta["concern"], meta["email"]),
                    daemon=True,
                )
                thread.start()
        except stripe.error.StripeError as e:
            print(f"[ERROR] Stripe: {e}", file=sys.stderr)

    return render_template("success.html")

# ── 無料診断ルート ────────────────────────────────────────────────

def generate_free_reading(birth_date: date, gender: str, concern: str) -> str:
    client = anthropic.Anthropic()
    zodiac     = get_zodiac_sign(birth_date)
    life_path  = get_life_path_number(birth_date)

    user_message = f"""
以下の情報をもとに、第1章から第3章まで3,000文字以上の鑑定文を生成してください。

【生年月日】{birth_date.strftime('%Y年%m月%d日')}
【太陽星座】{zodiac}
【ライフパスナンバー】{life_path}
【性別】{gender}
【お悩み】
{concern}
""".strip()

    result = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=6000,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT_FREE,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    return result.content[0].text

def generate_paid_reading(birth_date: date, gender: str, concern: str) -> str:
    client = anthropic.Anthropic()
    zodiac    = get_zodiac_sign(birth_date)
    life_path = get_life_path_number(birth_date)

    system = """あなたは「星詠み師 月詠」です。以下の2章を各1,500文字以上で生成してください。

【第4章】あなたが住むべき場所の条件
- 太陽星座・ライフパスナンバーから読み解く、最も波動が合う土地の特徴（気候/地形/都市規模/人のエネルギー）
- 逆に「合わない場所」の具体的な条件
- 今すぐできる「住む場所の波動チェック」方法

【第5章】スピリチュアル覚醒の具体的時期
- 入力された生年月日から、覚醒が加速し始める具体的な時期を「〇年〇月頃」で示す
- その時期に現れる5つのサイン
- 覚醒に備えて今から始めるべきこと3つ

文体：断言で語る。温かく詩的。AIとわからない人間の文章。"""

    user_message = f"【生年月日】{birth_date.strftime('%Y年%m月%d日')}\n【太陽星座】{zodiac}\n【ライフパスナンバー】{life_path}\n【性別】{gender}\n【お悩み】{concern}"

    result = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=6000,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return result.content[0].text

def generate_and_send_paid(birth_date_str: str, gender: str, concern: str, to_email: str):
    try:
        birth_date = date.fromisoformat(birth_date_str)
        content    = generate_paid_reading(birth_date, gender, concern)
        zodiac     = get_zodiac_sign(birth_date)
        life_path  = get_life_path_number(birth_date)
        html_body  = build_html_email(content, birth_date, zodiac, life_path)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🔓【解放】住むべき場所 × 覚醒時期の完全鑑定書が届きました"
        msg["From"]    = f"星詠み師 月詠 <{os.environ.get('FROM_EMAIL', os.environ['SMTP_USER'])}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        smtp_host = os.environ["SMTP_HOST"]
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            server.sendmail(msg["From"], to_email, msg.as_string())

        print(f"[OK] 有料鑑定送信完了 → {to_email}", flush=True)
    except Exception as e:
        print(f"[ERROR] generate_and_send_paid: {e}", file=sys.stderr, flush=True)

@app.route("/diagnose", methods=["GET", "POST"])
def diagnose():
    if request.method == "GET":
        return render_template("diagnose.html")

    birth_date_str = request.form.get("birth_date", "")
    gender         = request.form.get("gender", "")
    concern        = request.form.get("concern", "")
    email          = request.form.get("email", "")

    try:
        birth_date = date.fromisoformat(birth_date_str)
    except ValueError:
        return redirect("/diagnose")

    content   = generate_free_reading(birth_date, gender, concern)
    zodiac    = get_zodiac_sign(birth_date)
    life_path = get_life_path_number(birth_date)

    return render_template(
        "result.html",
        content       = content,
        zodiac        = zodiac,
        life_path     = life_path,
        birth_str     = birth_date.strftime("%Y年%m月%d日"),
        birth_date_raw= birth_date_str,
        gender        = gender,
        concern       = concern,
        email         = email,
    )

@app.route("/order-diagnose", methods=["POST"])
def order_diagnose():
    email  = request.form.get("email", "")
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "jpy",
                "product_data": {
                    "name": "スピリチュアル完全診断（住むべき場所 × 覚醒時期）",
                    "description": "最適な居住地の条件 + スピリチュアル覚醒の具体的時期",
                },
                "unit_amount": 1200,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=request.host_url + "success-diagnose?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.host_url + "diagnose",
        customer_email=email or None,
        metadata={
            "birth_date": request.form.get("birth_date", ""),
            "gender":     request.form.get("gender", ""),
            "concern":    request.form.get("concern", ""),
            "email":      email,
            "type":       "diagnose_paid",
        },
    )
    return redirect(session.url, 303)

@app.route("/success-diagnose")
def success_diagnose():
    session_id = request.args.get("session_id", "")
    if session_id and session_id not in _processed_sessions:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                _processed_sessions.add(session_id)
                meta = session.metadata
                thread = threading.Thread(
                    target=generate_and_send_paid,
                    args=(meta["birth_date"], meta["gender"], meta["concern"], meta["email"]),
                    daemon=True,
                )
                thread.start()
        except stripe.error.StripeError as e:
            print(f"[ERROR] Stripe: {e}", file=sys.stderr)

    return render_template("success.html")

# ── タロット鑑定ロジック ──────────────────────────────────────────

PROBLEM_LABELS = {
    "片思い":       "片思い中で、相手があなたをどう思っているか",
    "復縁":         "別れた相手との復縁を願っている状況",
    "浮気・秘密の恋": "公には言えない秘密の関係・複雑な恋愛状況",
    "相手の本音":   "今付き合っているまたは気になる相手の本当の気持ち",
}

def generate_tarot_free(card: dict, is_upright: bool, user_problem: str) -> str:
    client    = anthropic.Anthropic()
    orient    = "正位置" if is_upright else "逆位置"
    meaning   = card["upright"] if is_upright else card["reversed"]
    prob_desc = PROBLEM_LABELS.get(user_problem, user_problem)

    user_msg = f"""
【引いたカード】{card['name']}（{card['name_en']}） / {orient}
【悩みカテゴリー】{user_problem}（{prob_desc}）
【カードの意味 — {orient}】
- キーワード：{', '.join(meaning['keywords'])}
- 恋愛での意味：{meaning['love']}
- 相手の本音：{meaning['truth']}
- 未来：{meaning['future']}

①導入と②展開を出力し、③の有料壁テンプレートで締めてください。
""".strip()

    result = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2500,
        system=[{"type": "text", "text": TAROT_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    return result.content[0].text

def generate_tarot_paid(card: dict, is_upright: bool, user_problem: str) -> str:
    client    = anthropic.Anthropic()
    orient    = "正位置" if is_upright else "逆位置"
    meaning   = card["upright"] if is_upright else card["reversed"]

    system = f"""あなたはタロット占い師・神楽です。
有料鑑定として以下の2章を生成してください（合計1,500文字以上）。

【あの人の隠れた本音】（700〜800文字）
カードの意味を核に、相手が隠している本音を断言スタイルで読み解く。
悩みカテゴリー「{user_problem}」の状況に合わせた具体的なシナリオ。

【二人の最終的な結末】（700〜800文字）
3〜6ヶ月後の展開を「〇月頃に〇〇が起きる」という具体性で描く。
希望を持てる形で締める。

口調はカジュアルで辛口。AIっぽさ禁止。断言で語る。"""

    user_msg = f"""
【カード】{card['name']}（{orient}）
【キーワード】{', '.join(meaning['keywords'])}
【本音の意味】{meaning['truth']}
【未来の意味】{meaning['future']}
【悩み】{user_problem}
""".strip()

    result = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return result.content[0].text

def send_tarot_email(to_email: str, card: dict, is_upright: bool, content: str):
    orient = "正位置" if is_upright else "逆位置"
    body_html = ""
    for line in content.split("\n"):
        s = line.strip()
        if s.startswith("【") and "】" in s:
            body_html += f'<h2 style="color:#c9a84c;margin-top:28px;border-left:3px solid #7c3aed;padding-left:10px;font-size:1.0em;">{s}</h2>\n'
        elif s:
            body_html += f'<p style="margin:0 0 1em;line-height:2.1;">{s}</p>\n'

    html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#030308;font-family:'Hiragino Mincho ProN',Georgia,serif;">
<div style="max-width:640px;margin:0 auto;padding:40px 20px;">
  <div style="text-align:center;margin-bottom:32px;padding-bottom:24px;border-bottom:1px solid rgba(201,168,76,0.2);">
    <div style="font-size:1.6em;color:#c9a84c;letter-spacing:0.3em;margin-bottom:10px;">🔮</div>
    <h1 style="color:#c9a84c;font-size:1.4em;font-weight:normal;letter-spacing:0.15em;margin:0 0 8px;">タロット完全鑑定書</h1>
    <p style="color:#b090d0;font-size:0.85em;margin:0;">{card['name']}（{card['name_en']}）/ {orient}</p>
  </div>
  <div style="color:#ede0c4;line-height:2.1;font-size:0.98em;">{body_html}</div>
  <div style="text-align:center;margin-top:40px;padding-top:20px;border-top:1px solid rgba(201,168,76,0.2);color:#b090d0;font-size:0.82em;">
    タロット占い師 神楽（かぐら）
  </div>
</div></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔮【タロット完全鑑定】{card['name']}が示す「あの人の本音と最終結末」"
    msg["From"]    = f"タロット占い師 神楽 <{os.environ.get('FROM_EMAIL', os.environ['SMTP_USER'])}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        server.sendmail(msg["From"], to_email, msg.as_string())

def generate_and_send_tarot_paid(card_id: int, is_upright: bool, user_problem: str, email: str):
    try:
        card    = TAROT_DATA["cards"][card_id]
        content = generate_tarot_paid(card, is_upright, user_problem)
        send_tarot_email(email, card, is_upright, content)
        print(f"[OK] タロット有料鑑定送信完了 → {email}", flush=True)
    except Exception as e:
        print(f"[ERROR] tarot paid: {e}", file=sys.stderr, flush=True)

# ── タロット Flask ルーティング ───────────────────────────────────

@app.route("/tarot", methods=["GET"])
def tarot():
    cards_json = json.dumps(TAROT_DATA["cards"])
    return render_template("tarot.html", cards_json=cards_json)

@app.route("/tarot/reading", methods=["POST"])
def tarot_reading():
    card_id      = int(request.form.get("card_id", 0))
    is_upright   = request.form.get("is_upright", "true").lower() == "true"
    user_problem = request.form.get("user_problem", "相手の本音")
    email        = request.form.get("email", "")

    card    = TAROT_DATA["cards"][card_id]
    reading = generate_tarot_free(card, is_upright, user_problem)

    return render_template("tarot_result.html",
        reading      = reading,
        card         = card,
        is_upright   = is_upright,
        orient_label = "正位置" if is_upright else "逆位置",
        user_problem = user_problem,
        email        = email,
        card_id      = card_id,
    )

@app.route("/order-tarot", methods=["POST"])
def order_tarot():
    email        = request.form.get("email", "")
    card_id      = request.form.get("card_id", "0")
    is_upright   = request.form.get("is_upright", "true")
    user_problem = request.form.get("user_problem", "")
    card_name    = TAROT_DATA["cards"][int(card_id)]["name"]

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "jpy",
                "product_data": {
                    "name": f"タロット完全鑑定｜{card_name}が示すあの人の本音と最終結末",
                    "description": "あの人の隠れた本音 + 二人の最終的な結末を完全公開",
                },
                "unit_amount": 500,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=request.host_url + "success-tarot?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.host_url + "tarot",
        customer_email=email or None,
        metadata={
            "card_id":      card_id,
            "is_upright":   is_upright,
            "user_problem": user_problem,
            "email":        email,
            "type":         "tarot_paid",
        },
    )
    return redirect(session.url, 303)

@app.route("/success-tarot")
def success_tarot():
    session_id = request.args.get("session_id", "")
    if session_id and session_id not in _processed_sessions:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                _processed_sessions.add(session_id)
                meta = session.metadata
                thread = threading.Thread(
                    target=generate_and_send_tarot_paid,
                    args=(int(meta["card_id"]), meta["is_upright"] == "true",
                          meta["user_problem"], meta["email"]),
                    daemon=True,
                )
                thread.start()
        except stripe.error.StripeError as e:
            print(f"[ERROR] Stripe tarot: {e}", file=sys.stderr)
    return render_template("success.html")

# ── 起動 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
