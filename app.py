import os
import time
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage  # TextSendMessageを追加

# Flaskアプリケーションの設定
app = Flask(__name__)

# ==== LINE Bot API設定 ====
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in environment variables.")

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
except LineBotApiError as e:
    raise ValueError(f"Invalid LINE_CHANNEL_ACCESS_TOKEN: {str(e)}")

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==== 謎の問題データ ====
questions = [
    {
        "story_messages": [
            {"text": "第1問のストーリー", "delay_seconds": 1},
            {"text": "第1問のストーリー", "delay_seconds": 2}
        ],
        "puzzle_message": {"text": "第1問の問題文", "delay_seconds": 1.5},
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=XXXXX1", "delay_seconds": 2},
        "hint_keyword": "hint1",
        "hint_text":"第1問のヒント",
        "correct_answer": "correct1"
    },
    {
        "story_messages": [
            {"text": "第2問のストーリー", "delay_seconds": 2}
        ],
        "puzzle_message": {"text": "第2問の問題文", "delay_seconds": 1},
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=XXXXX2", "delay_seconds": 3},
        "hint_keyword": "hint2",
        "hint_text": "第2問のヒント",
        "correct_answer": "correct2"
    },
    {
        "story_messages": [
            {"text": "第3問のストーリー", "delay_seconds": 0.5},
            {"text": "第3問のストーリー", "delay_seconds": 1},
            {"text": "第3問のストーリー", "delay_seconds": 1.5}
        ],
        "puzzle_message": {"text": "第3問の問題文", "delay_seconds": 2},
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=XXXXX3", "delay_seconds": 1},
        "hint_keyword": "hint3",
        "hint_text": "第3問のヒント",
        "correct_answer": "correct3"
    },
    {
        "story_messages": [
            {"text": "第4問のストーリー", "delay_seconds": 1},
            {"text": "第4問のストーリー", "delay_seconds": 1}
        ],
        "puzzle_message": {"text": "第4問の問題文", "delay_seconds": 1.5},
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=XXXXX4", "delay_seconds": 2},
        "hint_keyword": "hint4",
        "hint_text": "第4問のヒント",
        "correct_answer": "correct4"
    },
    {
        "story_messages": [
            {"text": "第5問のストーリー", "delay_seconds": 1}
        ],
        "puzzle_message": {"text": "第5問の問題文", "delay_seconds": 1},
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=XXXXX5", "delay_seconds": 1.5},
        "hint_keyword": "hint5",
        "hint_text": "第5問のヒント",
        "correct_answer": ["correct5a", "correct5b"],  # 正解が2つ（correct5aとcorrect5b）
        "good_end_story": [
            {"text": "Goodエンドのストーリー", "delay_seconds": 1},
            {"text": "Goodエンドのストーリー", "delay_seconds": 1}
        ],
        "bad_end_story": [
            {"text": "Badエンドのストーリー", "delay_seconds": 1},
            {"text": "Badエンドのストーリー", "delay_seconds": 1}
        ]
    },
    {
        "story_messages": [
            {"text": "終章のストーリー", "delay_seconds": 1},
            {"text": "終章のストーリー", "delay_seconds": 1}
        ],
        "puzzle_message": {"text": "終章のおまけ謎", "delay_seconds": 2},
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=XXXXX6", "delay_seconds": 1},
        "hint_keyword": "hint6",
        "hint_text": "終章のヒント",
        "correct_answer": "correct6"
    }
]

# ==== ユーザーごとの進行状況と回答 ====
user_states = {}  # {user_id: {"current_q": int, "answers": [list of answers]}}

# ==== 関数: 問題またはストーリーを送信 ====
def send_content(user_id, content_type, content_data, next_qnum=None):
    try:
        if content_type == "question":
            q = content_data
            for story_msg in q["story_messages"]:
                line_bot_api.push_message(user_id, TextSendMessage(text=story_msg["text"]))
                time.sleep(story_msg["delay_seconds"])
            line_bot_api.push_message(user_id, TextSendMessage(text=q["puzzle_message"]["text"]))
            time.sleep(q["puzzle_message"]["delay_seconds"])
            line_bot_api.push_message(
                user_id,
                ImageSendMessage(original_content_url=q["image_url"]["url"], preview_image_url=q["image_url"]["url"])
            )
            time.sleep(q["image_url"]["delay_seconds"])
            line_bot_api.push_message(user_id, TextSendMessage(text="答えとなるテキストを送ってね！"))
        elif content_type == "end_story":
            for story_msg in content_data:
                line_bot_api.push_message(user_id, TextSendMessage(text=story_msg["text"]))
                time.sleep(story_msg["delay_seconds"])
            if next_qnum is not None:
                send_question(user_id, next_qnum)
    except LineBotApiError as e:
        print(f"Failed to send content to {user_id}: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}")
        raise

def send_question(user_id, qnum):
    if qnum < len(questions):
        send_content(user_id, "question", questions[qnum])
    else:
        line_bot_api.push_message(user_id, TextSendMessage(text="全ての問題が終了しました！"))

# ==== Webhookエンドポイント ====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    print(f"Received body at {os.getcwd()}: {body}")
    print(f"Signature: {signature}")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature error")
        return "Invalid signature", 400
    except Exception as e:
        print(f"Callback error: {str(e)}")
        return "Internal server error", 500
    return "OK", 200

# ==== メッセージ受信時の処理 ====
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text.lower() == "start":
        user_states[user_id] = {"current_q": 0, "answers": []}
        send_question(user_id, 0)
        return

    if user_id in user_states:
        qnum = user_states[user_id]["current_q"]
        if qnum < len(questions):
            q = questions[qnum]
            if text.lower() == q["hint_keyword"].lower():
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=q["hint_text"])
                )
                return
            elif qnum < 4 and text.lower() == q["correct_answer"].lower():  # 1〜4問
                user_states[user_id]["current_q"] += 1
                send_question(user_id, user_states[user_id]["current_q"])
                return
            elif qnum == 4 and text.lower() in q["correct_answer"]:  # 第5問の正解1/2
                if text.lower() == q["correct_answer"][0]:  # correct5a → Goodエンド
                    send_content(user_id, "end_story", q["good_end_story"], 5)
                elif text.lower() == q["correct_answer"][1]:  # correct5b → Badエンド
                    send_content(user_id, "end_story", q["bad_end_story"], 5)
                return
            elif qnum == 4 and text.lower() not in q["correct_answer"]:  # 第5問の不正解
                send_content(user_id, "end_story", q["bad_end_story"], 5)
                return
            elif qnum == 5 and text.lower() == q["correct_answer"].lower():  # 終章のおまけ謎
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="大正解！"))
                user_states[user_id]["current_q"] += 1
                send_question(user_id, user_states[user_id]["current_q"])
                return
            else:  # 不正解
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"残念。不正解です。{q['hint_keyword']}と送ると何かあるかも"))
                return

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="メッセージを理解できませんでした。"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
