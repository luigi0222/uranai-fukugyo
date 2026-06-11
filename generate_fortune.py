#!/usr/bin/env python3
"""
占い鑑定書 自動生成スクリプト
使い方: python generate_fortune.py
"""

import anthropic
import os
import sys
from datetime import date
from pathlib import Path

SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"
OUTPUT_DIR = Path(__file__).parent / "output"

# ── 占術計算 ──────────────────────────────────────────────────────

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
    """数秘術：ライフパスナンバー（生年月日の数字を1桁になるまで足す）"""
    total = sum(int(c) for c in d.strftime("%Y%m%d"))
    while total > 9 and total not in (11, 22, 33):
        total = sum(int(c) for c in str(total))
    return total

# ── ユーザー入力 ──────────────────────────────────────────────────

def get_user_input() -> dict:
    print("\n" + "=" * 50)
    print("  ✨ 星詠み 鑑定書 自動生成システム ✨")
    print("=" * 50 + "\n")

    while True:
        try:
            birth_str = input("生年月日を入力してください (例: 1995-07-15): ").strip()
            birth_date = date.fromisoformat(birth_str)
            break
        except ValueError:
            print("  ⚠ 形式が正しくありません。YYYY-MM-DD で入力してください。")

    gender = input("性別を入力してください (女性 / 男性): ").strip()

    print("具体的なお悩みを入力してください（書き終わったら空行でEnter）:")
    lines = []
    while True:
        line = input()
        if not line and lines:
            break
        lines.append(line)
    concern = "\n".join(lines).strip()

    zodiac = get_zodiac_sign(birth_date)
    life_path = get_life_path_number(birth_date)

    print(f"\n  🔮 太陽星座：{zodiac}")
    print(f"  🔢 ライフパスナンバー：{life_path}\n")

    return {
        "birth_date": birth_date,
        "gender": gender,
        "concern": concern,
        "zodiac": zodiac,
        "life_path": life_path,
    }

# ── Claude API 呼び出し ───────────────────────────────────────────

def generate_fortune(user: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("❌ 環境変数 ANTHROPIC_API_KEY が設定されていません。")

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    user_message = f"""
以下の情報をもとに、第一章から第六章まで10,000文字以上の本格鑑定書を作成してください。
章の見出しは「【第〇章】タイトル」の形式で、各章を丁寧に展開してください。

【生年月日】{user['birth_date'].strftime('%Y年%m月%d日')}
【太陽星座】{user['zodiac']}
【ライフパスナンバー】{user['life_path']}
【性別】{user['gender']}
【お悩み】
{user['concern']}
""".strip()

    print("🔮 鑑定書を生成中...（しばらくお待ちください）\n")
    print("-" * 50)

    content = ""
    # ephemeral キャッシュでシステムプロンプト（長文）のコストを削減
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=16000,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            content += text

    print("\n" + "-" * 50)
    return content

# ── HTML 出力（印刷→PDFに対応したデザイン） ───────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>星詠み 完全鑑定書</title>
<style>
  :root {{
    --gold: #c9a84c;
    --purple-dark: #1a0533;
    --purple-mid: #2d0b5c;
    --text-main: #f0e4ff;
    --text-sub: #b090d0;
    --accent: #9b59b6;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: "Hiragino Mincho ProN", "Yu Mincho", "ヒラギノ明朝 ProN", Georgia, serif;
    background: linear-gradient(160deg, var(--purple-dark) 0%, var(--purple-mid) 60%, var(--purple-dark) 100%);
    color: var(--text-main);
    min-height: 100vh;
    padding: 40px 20px;
    line-height: 2.0;
  }}

  .wrapper {{
    max-width: 820px;
    margin: 0 auto;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(200, 150, 255, 0.25);
    border-radius: 20px;
    padding: 70px 80px;
    box-shadow: 0 0 80px rgba(120, 40, 255, 0.15), inset 0 1px 0 rgba(255,255,255,0.07);
  }}

  .cover {{
    text-align: center;
    margin-bottom: 60px;
    padding-bottom: 50px;
    border-bottom: 1px solid rgba(200,150,255,0.2);
  }}

  .cover-ornament {{
    font-size: 2.4em;
    letter-spacing: 0.3em;
    color: var(--gold);
    margin-bottom: 20px;
  }}

  .cover h1 {{
    font-size: 1.9em;
    color: var(--gold);
    letter-spacing: 0.15em;
    margin-bottom: 16px;
    font-weight: normal;
  }}

  .cover .meta {{
    color: var(--text-sub);
    font-size: 0.95em;
    line-height: 2.0;
  }}

  .content {{
    white-space: pre-wrap;
    word-break: break-all;
    font-size: 1.05em;
  }}

  /* 章見出し */
  .content :is(h2, h3) {{
    color: var(--gold);
    margin-top: 50px;
    margin-bottom: 20px;
    font-size: 1.15em;
    letter-spacing: 0.08em;
    border-left: 3px solid var(--accent);
    padding-left: 14px;
  }}

  .footer {{
    text-align: center;
    margin-top: 60px;
    padding-top: 30px;
    border-top: 1px solid rgba(200,150,255,0.2);
    color: var(--text-sub);
    font-size: 0.85em;
    line-height: 2.0;
  }}

  /* 印刷時：白背景に切り替え */
  @media print {{
    body {{ background: white; color: #1a1a1a; }}
    .wrapper {{ background: white; border: none; box-shadow: none; padding: 40px; }}
    .cover h1, .content :is(h2,h3) {{ color: #4a0080; }}
    .cover-ornament {{ color: #7a5c00; }}
    .cover .meta, .footer {{ color: #555; }}
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="cover">
    <div class="cover-ornament">✦ ✦ ✦</div>
    <h1>星詠み 完全鑑定書</h1>
    <div class="meta">
      {birth_str}生 &nbsp;|&nbsp; {zodiac} &nbsp;|&nbsp; ライフパス {life_path}<br>
      鑑定日：{today}
    </div>
  </div>

  <div class="content">{body}</div>

  <div class="footer">
    ✦ この鑑定書はあなただけのために紡がれた言葉です ✦<br>
    星詠み師 月詠（つきよみ）
  </div>
</div>
</body>
</html>
"""

def markdown_to_html_inline(text: str) -> str:
    """最低限の Markdown → HTML 変換（章見出しのみ対応）"""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("### "):
            lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("**") and stripped.endswith("**"):
            lines.append(f"<strong>{stripped[2:-2]}</strong>")
        else:
            lines.append(line)
    return "\n".join(lines)

def save_as_html(content: str, user: dict) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = user["birth_date"].strftime("%Y%m%d")
    zodiac_short = user["zodiac"][:2]
    output_path = OUTPUT_DIR / f"鑑定書_{stamp}_{zodiac_short}.html"

    body = markdown_to_html_inline(content)
    html = HTML_TEMPLATE.format(
        birth_str=user["birth_date"].strftime("%Y年%m月%d日"),
        zodiac=user["zodiac"],
        life_path=user["life_path"],
        today=date.today().strftime("%Y年%m月%d日"),
        body=body,
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path

# ── エントリーポイント ────────────────────────────────────────────

def main():
    user = get_user_input()
    content = generate_fortune(user)
    output_path = save_as_html(content, user)

    print(f"\n✅ 保存完了：{output_path.resolve()}")
    print("📄 PDFにするには：ブラウザで開く → 印刷（Cmd+P）→「PDFに保存」")

    # Mac ならブラウザで自動オープン
    if sys.platform == "darwin":
        os.system(f'open "{output_path}"')

if __name__ == "__main__":
    main()
