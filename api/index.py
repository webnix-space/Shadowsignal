from flask import Flask, jsonify

# THIS MUST BE THE FIRST THING AT MODULE LEVEL
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "ShadowSignal is running"})

@app.route('/api/test')
def test():
    return jsonify({"status": "ok", "agents": 5, "band": True})

# Vercel handler
handler = app

if __name__ == '__main__':
    app.run(debug=True, port=5000)
