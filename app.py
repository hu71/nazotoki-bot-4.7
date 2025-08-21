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

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
except LineBotApiError as e:
    raise ValueError(f"Invalid LINE_CHANNEL_ACCESS_TOKEN: {str(e)}")

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==== 謎の問題データ ====
questions = [
    {
        "text":'''「やっほー！新米探偵さん！」
；画面に探偵姿の少女が現れ、元気に
「わたしは探偵所の新人サポート AI,サクラだよ。よろしくねー！」
「ここに来てるってことは、君は探偵見習いだよね？サクラの仕事は、 忙しいオサダ所
長に代わって新人さんの推理力を鍛えること！」
「では早速、問題です！探偵見習いのテストです。 制限時間は……所長が帰ってくるま
でにしましょう。困ったら頭をひっくり返して、最初から考えてみるといいですよ」''',
        "image_url": "https://drive.google.com/file/d/1vxITAOfyz234ZFTapvFhrS3re4y6X0sG/view?usp=drivesdk",
        "hint_keyword": "hint1"
        "hint_text": "0,2,5…"
   
    },
    {
        "text": "第2問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX2",
        "hint_keyword": "hint2",
        "hint_text": "第2問のヒント"
    },
    {
        "text": "第3問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX3",
        "hint_keyword": "hint3",
        "hint_text": "第3問のヒント"
    },
    {
        "text": "第4問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX4",
        "hint_keyword": "hint4",
        "hint_text": "第4問のヒント"
    },
    {
        "text": "第5問のストーリーと問題文",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX5",
        "hint_keyword": "hint5",
        "hint_text": "第5問のヒント"
    },
    {
        "text": "終章: 最後の問題",
        "image_url": "https://drive.google.com/uc?export=view&id=XXXXX6",
        "hint_keyword": "hint6",
        "hint_text": "最後のヒント"
    }
]

# ==== ユーザーごとの進行状況と回答 ====
user_states = {}        # {user_id: {"current_q": int, "answers": [list of answers]}}
pending_judges = []     # [{"user_id": str, "qnum": int, "img_url": str}]
judged_history = []     # [{"user_id": str, "qnum": int, "img_url": str, "result": str}]

# ==== 関数: 問題を送信 ====
def send_question(user_id, qnum):
    if qnum < len(questions):
        q = questions[qnum]
        try:
            line_bot_api.push_message(
                user_id,
                [
                    TextSendMessage(text=q["text"]),
                    ImageSendMessage(original_content_url=q["image_url"], preview_image_url=q["image_url"]),
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
        os.makedirs("/tmp", exist_ok=True)
        with open(temp_path, "wb") as f:
            for chunk in message_content.iter_content(chunk_size=1024):
                f.write(chunk)

        if not os.path.exists(temp_path):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：画像を保存できませんでした。"))
            return

        # 静的フォルダにコピー
        static_path = os.path.join(app.static_folder, unique_filename)
        with open(static_path, "wb") as f:
            with open(temp_path, "rb") as temp_f:
                f.write(temp_f.read())

        # ホストURLを安全に取得
        host_url = request.host_url if request.host_url else os.environ.get("RENDER_EXTERNAL_URL", "https://nazotoki-bot-4-7-2.onrender.com")
        img_url = f"{host_url.rstrip('/')}/static/{unique_filename}"
        pending_judges.append({"user_id": user_id, "qnum": qnum, "img_url": img_url})

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="判定中です。しばらくお待ちください！"))

    except LineBotApiError as e:
        print(f"LineBotApi error: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}, Error details: {getattr(e, 'error_details', 'N/A')}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：API接続に失敗しました。"))
    except PermissionError as pe:
        print(f"Permission error: {str(pe)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：書き込み権限がありません。"))
    except IOError as ioe:
        print(f"IO error: {str(ioe)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：ファイル操作に失敗しました。"))
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像の処理中にエラーが発生しました。もう一度試してください。"))

# ==== 判定フォーム ====
@app.route("/judge", methods=["GET", "POST"])
def judge():
    global pending_judges, judged_history

    if request.method == "POST":
        user_id = request.form.get("user_id")
        qnum = request.form.get("qnum")
        result = request.form.get("result")

        # POSTデータが全て揃っていて、pending_judgesに該当データがある場合のみ処理
        if user_id and qnum and result:
            try:
                qnum = int(qnum)
                # 対応するpending_judgesエントリが存在するか確認
                judge_to_process = next((j for j in pending_judges if j["user_id"] == user_id and j["qnum"] == qnum), None)
                if judge_to_process:
                    if qnum == 4:
                        if result == "correct1":
                            line_bot_api.push_message(user_id, TextSendMessage(text="大正解！ Goodエンディング"))
                        elif result == "correct2":
                            line_bot_api.push_message(user_id, TextSendMessage(text="正解！ Badエンディング"))
                        else:
                            line_bot_api.push_message(user_id, TextSendMessage(text="残念。不正解です。もう一度挑戦してみよう！"))
                    elif qnum == 5:
                        if result == "correct":
                            line_bot_api.push_message(user_id, TextSendMessage(text="大正解！ クリア特典"))
                        else:
                            line_bot_api.push_message(user_id, TextSendMessage(text="残念。不正解です。もう一度挑戦してみよう！"))
                    else:
                        if result == "correct":
                            line_bot_api.push_message(user_id, TextSendMessage(text="大正解！"))
                            if user_id in user_states:
                                user_states[user_id]["current_q"] += 1
                                send_question(user_id, user_states[user_id]["current_q"])
                        else:
                            line_bot_api.push_message(user_id, TextSendMessage(text="残念。不正解です。もう一度挑戦してみよう！"))

                    judged_history.append({
                        "user_id": user_id,
                        "qnum": qnum,
                        "img_url": judge_to_process["img_url"],
                        "result": result
                    })
                    pending_judges = [j for j in pending_judges if not (j["user_id"] == user_id and j["qnum"] == qnum)]
            except LineBotApiError as e:
                print(f"Failed to send result to {user_id}: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}")
                return "API error", 500
            except ValueError:
                print(f"Invalid qnum: {qnum}")
                return "Invalid data", 400

    return render_template("judge.html", judges=pending_judges, history=judged_history)
