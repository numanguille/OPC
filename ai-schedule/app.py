from flask import Flask, request, jsonify
from flask_cors import CORS
import os

# 导入你的讯飞OCR脚本
from xunfei_ocr_v2 import ocr_recognize, parse_text

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route('/ocr', methods=['POST'])
def ocr_api():

    if 'image' not in request.files:
        return jsonify({
            "text": "未收到图片"
        })

    file = request.files['image']

    image_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    file.save(image_path)

    try:

        # 调用讯飞OCR
        result = ocr_recognize(image_path)

        # 提取纯文本
        text = parse_text(result)

        return jsonify({
            "text": text
        })

    except Exception as e:

        return jsonify({
            "text": f"OCR识别失败: {str(e)}"
        })


if __name__ == '__main__':
    import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)