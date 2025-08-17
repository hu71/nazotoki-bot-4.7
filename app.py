import os
import uuid
from flask import Flask, request, render_template, redirect, url_for
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage

app = Flask(__name__, static_url_path='/static', static_folder='static')

# ==== LINE Bot API設定 ====
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in environment variables.")

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    print("LINE Bot API initialized successfully.")
except LineBotApiError as e:
    raise ValueError(f"Invalid LINE_CHANNEL_ACCESS_TOKEN: {str(e)}")

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==== 謎の問題データ ====
questions = [
    {"text": "第1問のストーリーと問題文", "image_url": "https://drive.google.com/uc?export=view&id=XXXXX1", "hint_keyword": "hint1", "hint_text": "第1問のヒントです"},
    {"text": "第2問のストーリーと問題文", "image_url": "https://drive.google.com/uc?export=view&id=XXXXX2", "hint_keyword": "hint2", "hint_text": "第2問のヒントです"},
    {"text": "第3問のストーリーと問題文", "image_url": "https://drive.google.com/uc?export=view&id=XXXXX3", "hint_keyword": "hint3", "hint_text": "第3問のヒントです"},
    {"text": "第4問のストーリーと問題文", "image_url": "https://drive.google.com/uc?export=view&id=XXXXX4", "hint_keyword": "hint4", "hint_text": "第4問のヒントです"},
    {"text": "第5問のストーリーと問題文", "image_url": "https://drive.google.com/uc?export=view&id=XXXXX5", "hint_keyword": "hint5", "hint_text": "第5問のヒントです"},
    {"text": "終章: 最後の問題", "image_url": "https://drive.google.com/uc?export=view&id=XXXXX6", "hint_keyword": "hint6", "hint_text": "最後のヒントです"}
]

user_states = {}
pending_judges = []
judged_history = []

def send_question(user_id, qnum):
    if qnum < len(questions):
        q = questions[qnum]
        try:
            line_bot_api.push_message(
                user_id,
                [TextSendMessage(text=q["text"]), ImageSendMessage(original_content_url=q["image_url"], preview_image_url=q["image_url"]), TextSendMessage(text="答えとなるものの写真を送ってね！")]
            )
            print(f"Message sent to {user_id} for question {qnum}")
        except LineBotApiError as e:
            print(f"API error for {user_id}: {str(e)} - Status: {getattr(e, 'status_code', 'N/A')}")
            raise RuntimeError(f"Failed to send question to {user_id}: {str(e)}")
    else:
        line_bot_api.push_message(user_id, TextSendMessage(text="全ての問題が終了しました！"))
        print(f"End message sent to {user_id}")

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    print(f"Received request at {os.getcwd()}: {body[:100]}...")
    try:
        handler.handle(body, signature)
        print("Handler processed request successfully")
    except InvalidSignatureError:
        print("Invalid signature error - Signature: {}, Body: {}".format(signature, body[:50]))
        return "Invalid signature", 400
    except Exception as e:
        print(f"Callback error: {str(e)} - Body: {body[:50]}")
        return "Internal server error", 500
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    print(f"Received text from {user_id}: {text} - Event: {event}")

    if text.lower() == "start":
        user_states[user_id] = {"current_q": 0, "answers": []}
        print(f"Initialized state for {user_id}: {user_states[user_id]}")
        send_question(user_id, 0)
        return

    if user_id in user_states:
        qnum = user_states[user_id]["current_q"]
        if qnum < len(questions) and text.lower() == questions[qnum]["hint_keyword"].lower():
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=questions[qnum]["hint_text"]))
            print(f"Hint sent to {user_id} for question {qnum}")
            return

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="メッセージを理解できませんでした."))
    print(f"Default response sent to {user_id}")

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    print(f"Received image from {user_id} - Event: {event}")

    if user_id not in user_states:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="まずは『start』と送って始めてね！"))
        print(f"Start prompt sent to {user_id}")
        return

    qnum = user_states[user_id]["current_q"]

    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        unique_filename = f"{user_id}_{qnum}_{uuid.uuid4()}.jpg"
        temp_path = f"/tmp/{unique_filename}"
        static_path = f"static/{unique_filename}"

        os.makedirs("/tmp", exist_ok=True)
        with open(temp_path, "wb") as f:
            for chunk in message_content.iter_content(chunk_size=1024):
                f.write(chunk)

        if not os.path.exists(temp_path):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：画像を保存できませんでした。"))
            print(f"Image save failed for {user_id}")
            return

        os.makedirs("static", exist_ok=True)
        os.rename(temp_path, static_path)

        host_url = request.host_url if request.host_url else "https://your-render-app.onrender.com"  # 実際のURLに置き換え
        img_url = f"{host_url.rstrip('/')}/{static_path}"
        pending_judges.append({"user_id": user_id, "qnum": qnum, "img_url": img_url})
        print(f"Added to pending judges: {img_url}")

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="判定中です。しばらくお待ちください！"))
        print(f"Processing response sent to {user_id}")

    except LineBotApiError as e:
        print(f"LineBotApi error for {user_id}: {str(e)} - Status: {getattr(e, 'status_code', 'N/A')}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：API接続に失敗しました。"))
    except PermissionError as e:
        print(f"Permission error for {user_id}: {str(e)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：書き込み権限がありません。"))
    except IOError as e:
        print(f"IO error for {user_id}: {str(e)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：ファイル操作に失敗しました。"))
    except Exception as e:
        print(f"Unexpected error for {user_id}: {str(e)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像の処理中にエラーが発生しました。もう一度試してください。"))

@app.route("/judge", methods=["GET", "POST"])
def judge():
    global pending_judges, judged_history

    if request.method == "POST":
        user_id = request.form.get("user_id", "")
        qnum = request.form.get("qnum", "")
        result = request.form.get("result", "")

        try:
            qnum = int(qnum) if qnum else 0
            if not user_id or qnum < 0 or qnum >= len(questions) or not result:
                return "Invalid request data", 400

            if qnum == 4:
                if result == "correct1":
                    line_bot_api.push_message(user_id, TextSendMessage(text="大正解！ Goodエンディング！"))
                elif result == "correct2":
                    line_bot_api.push_message(user_id, TextSendMessage(text="正解！ Badエンディング！"))
                else:
                    line_bot_api.push_message(user_id, TextSendMessage(text="残念。不正解です。もう一度挑戦してみよう！"))
            elif qnum == 5:
                if result == "correct":
                    line_bot_api.push_message(user_id, TextSendMessage(text="大正解！ クリア特典があるよ。探偵事務所にお越しください。"))
                else:
                    line_bot_api.push_message(user_id, TextSendMessage(text="残念。不正解です。もう一度挑戦してみよう！"))
            else:
                if result == "correct":
                    line_bot_api.push_message(user_id, TextSendMessage(text="大正解！"))
                    user_states[user_id]["current_q"] += 1
                    send_question(user_id, user_states[user_id]["current_q"])
                else:
                    line_bot_api.push_message(user_id, TextSendMessage(text="残念。不正解です。もう一度挑戦してみよう！"))

            for j in pending_judges:
                if j["user_id"] == user_id and j["qnum"] == qnum:
                    judged_history.append({"user_id": user_id, "qnum": qnum, "img_url": j["img_url"], "result": result})
            pending_judges = [j for j in pending_judges if not (j["user_id"] == user_id and j["qnum"] == qnum)]
        except LineBotApiError as e:
            print(f"Judge API error for {user_id}: {str(e)} - Status: {getattr(e, 'status_code', 'N/A')}")
            return f"API error: {str(e)}", 500
        except (ValueError, KeyError):
            return "Invalid request data", 400

        return redirect(url_for("judge"))

    return render_template("judge.html", judges=pending_judges, history=judged_history)
