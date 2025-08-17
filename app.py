import os
import uuid
from flask import Flask, request, render_template, redirect, url_for
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage

# Flaskアプリケーションの設定
app = Flask(__name__, static_url_path='/static', static_folder='static')

# ==== LINE Bot API設定 ====
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in environment variables.")

print(f"Loaded LINE_CHANNEL_ACCESS_TOKEN: {repr(LINE_CHANNEL_ACCESS_TOKEN)} (Length: {len(LINE_CHANNEL_ACCESS_TOKEN)})")
print(f"Loaded LINE_CHANNEL_SECRET: {repr(LINE_CHANNEL_SECRET)} (Length: {len(LINE_CHANNEL_SECRET)})")

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    test_response = line_bot_api.get_profile("dummy_user_id")
    print("LINE Bot API initialized and token validated successfully.")
except LineBotApiError as e:
    print(f"Failed to initialize LINE Bot API: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}, Error details: {getattr(e, 'error_details', 'N/A')}")
    raise

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==== 謎の問題データ ====
questions = [
    {
        "text": "第1問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX1",
        "hint_keyword": "hint1",
        "hint_text": "第1問のヒントです"
    },
    {
        "text": "第2問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX2",
        "hint_keyword": "hint2",
        "hint_text": "第2問のヒントです"
    },
    {
        "text": "第3問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX3",
        "hint_keyword": "hint3",
        "hint_text": "第3問のヒントです"
    },
    {
        "text": "第4問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX4",
        "hint_keyword": "hint4",
        "hint_text": "第4問のヒントです"
    },
    {
        "text": "第5問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX5",
        "hint_keyword": "hint5",
        "hint_text": "第5問のヒントです"
    },
    {
        "text": "終章: 最後の問題",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX6",
        "hint_keyword": "hint6",
        "hint_text": "最後のヒントです"
    }
]

# ==== ユーザーごとの進行状況と回答 ====
user_states = {}        # {user_id: {"current_q": int, "answers": [list of answers]}}
pending_judges = []     # [{user_id, qnum, img_url}]
judged_history = []     # [{user_id, qnum, img_url, result}]

# ==== 関数: 問題を送信 ====
def send_question(user_id, qnum):
    if qnum < len(questions):
        q = questions[qnum]
        try:
            line_bot_api.push_message(
                user_id,
                [
                    TextSendMessage(text=q["text"]),
                    ImageSendMessage(
                        original_content_url=q["image_url"],
                        preview_image_url=q["image_url"]
                    ),
                    TextSendMessage(text="答えとなるものの写真を送ってね！")
                ]
            )
        except LineBotApiError as e:
            print(f"Failed to send question to {user_id}: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}")
            raise
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
        if qnum < len(questions) and text.lower() == questions[qnum]["hint_keyword"].lower():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=questions[qnum]["hint_text"])
            )
            return

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="メッセージを理解できませんでした。"))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id

    if user_id not in user_states:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="まずは『start』と送って始めてね！"))
        return

    qnum = user_states[user_id]["current_q"]

    try:
        print(f"Fetching image for user {user_id}, question {qnum}")
        message_content = line_bot_api.get_message_content(event.message.id)
        
        # 一意のファイル名を生成
        unique_filename = f"{user_id}_{qnum}_{uuid.uuid4()}.jpg"
        temp_path = f"/tmp/{unique_filename}"
        static_path = f"static/{unique_filename}"

        print(f"Checking write permission for: {temp_path}")
        os.makedirs("/tmp", exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(message_content.content)

        if not os.path.exists(temp_path):
            print("Image file was not created")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：画像を保存できませんでした。"))
            return

        # /tmpからstaticに移動
        os.makedirs("static", exist_ok=True)
        os.rename(temp_path, static_path)

        img_url = f"{request.host_url.rstrip('/')}/{static_path}"
        print(f"Generated img_url: {img_url}")
        pending_judges.append({"user_id": user_id, "qnum": qnum, "img_url": img_url})

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="判定中です。しばらくお待ちください！"))

    except LineBotApiError as lbae:
        print(f"LineBotApi error: {str(lbae)} - Status code: {getattr(lbae, 'status_code', 'N/A')}, Error details: {getattr(lbae, 'error_details', 'N/A')}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：API接続に失敗しました。"))
    except PermissionError as pe:
        print(f"Permission error: {str(pe)} - Check directory permissions at {os.getcwd()}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：書き込み権限がありません。"))
    except IOError as ioe:
        print(f"IO error: {str(ioe)} - Verify disk space or permissions at {os.getcwd()}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：ファイル操作に失敗しました。"))
    except Exception as e:
        print(f"Unexpected error in handle_image: {str(e)} - Please check logs")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像の処理中にエラーが発生しました。もう一度試してください。"))

# ==== 判定フォーム ====
@app.route("/judge", methods=["GET", "POST"])
def judge():
    global pending_judges, judged_history

    if request.method == "POST":
        user_id = request.form["user_id"]
        qnum_str = request.form.get("qnum", "")  # デフォルト値として空文字を指定
        result = request.form["result"]

        # qnumを整数に変換する前にバリデーション
        try:
            qnum = int(qnum_str) if qnum_str.isdigit() else -1
            if qnum < 0 or qnum >= len(questions):
                raise ValueError(f"Invalid qnum: {qnum_str}")
        except ValueError as e:
            print(f"ValueError in judge: {str(e)} - qnum_str was {qnum_str}")
            return "Invalid question number", 400

        try:
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
                    judged_history.append({
                        "user_id": user_id,
                        "qnum": qnum,
                        "img_url": j["img_url"],
                        "result": result
                    })
            pending_judges = [j for j in pending_judges if not (j["user_id"] == user_id and j["qnum"] == qnum)]
        except LineBotApiError as e:
            print(f"Failed to send result to {user_id}: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}")
            return "API error", 500

        return redirect(url_for("judge"))

    return render_template("judge.html", judges=pending_judges, history=judged_history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
