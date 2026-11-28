"""Dựng request webhook SePay GIẢ có chữ ký HMAC-SHA256 cho selfcheck (2026-11-28).

Dùng chung `sepay.sepay_signature` với code thật. Body là bytes tự serialize (đúng bytes được ký), Content-Type JSON.
Mỗi lần gọi lấy một timestamp KHÁC, tăng dần (giờ hiện tại, hoặc lần trước + 1 nếu cùng giây) để hai request cùng body
không trùng chữ ký (webhook chống phát lại theo chữ ký đã xử lý thành công).
"""

import json
import time

WEBHOOK_PATH = "/api/method/mypos.mypos.doctype.sepay.sepay.sepay_webhook"
_last = [0]


def next_timestamp():
	_last[0] = max(int(time.time()), _last[0] + 1)
	return str(_last[0])


def webhook_environ(payload=None, secret=None, *, body=None, timestamp=None, signature=None, headers=None,
		query_string=None):
	"""environ WSGI của request webhook.

	payload: dict -> body JSON (bỏ qua khi truyền `body` bytes).
	secret: None -> KHÔNG gửi header chữ ký; có -> ký "{timestamp}." + body.
	signature: ghi đè chữ ký (vd. chữ ký của body khác). headers: thêm header (vd. Authorization).
	"""
	from werkzeug.test import EnvironBuilder

	from mypos.mypos.doctype.sepay import sepay as S

	if body is None:
		body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
	hdrs = dict(headers or {})
	if secret is not None:
		ts = timestamp if timestamp is not None else next_timestamp()
		hdrs[S.TIMESTAMP_HEADER] = str(ts)
		hdrs[S.SIGNATURE_HEADER] = signature or S.sepay_signature(secret, ts, body)
	return EnvironBuilder(method="POST", path=WEBHOOK_PATH, data=body, content_type="application/json",
		headers=hdrs, query_string=query_string).get_environ()


def webhook_request(payload=None, secret=None, **kw):
	"""werkzeug Request cho frappe.local.request (xem webhook_environ)."""
	from werkzeug.wrappers import Request

	return Request(webhook_environ(payload, secret, **kw))
