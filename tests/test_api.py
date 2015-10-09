# coding:utf-8

from __future__ import unicode_literals
from __future__ import absolute_import
from flask import Flask, Blueprint, request, url_for
from flask_restaction import Api, Resource
from datetime import datetime
import pytest
from mock import Mock, patch


def test_parse_request():
    class Hello(Resource):

        def get(self):
            return "hello"

    app = Flask(__name__)
    app.debug = True
    bp = Blueprint("blueprint", __name__)
    api = Api(bp)
    api.add_resource(Hello)
    app.register_blueprint(bp, url_prefix="/api")
    with app.test_client() as c:
        rv = c.get("/api/hello")
        assert b"hello" in rv.data
        assert request.resource == "hello"
        assert request.action == "get"
        assert request.me["id"] is None


def create_api():
    class Hello(Resource):
        schema_name = ("name", {
            "desc": "name",
            "required": True,
            "validate": "name",
            "default": "world"
        })
        schema_date = ("date", {
            "desc": "date",
            "required": True,
            "validate": "datetime",
        })
        schema_hello = ("hello", {
            "desc": "hello",
            "required": True,
            "validate": "unicode",
        })
        schema_inputs = {
            "get": dict([schema_name]),
            "post_login": dict([schema_date]),
        }
        schema_outputs = {
            "get": dict([schema_hello]),
            "get_error": dict([schema_hello]),
            "post_login": dict([schema_hello]),
        }

        def get(self, name):
            return {"hello": name}

        def get_error(self):
            raise ValueError("get_error")

        def post_login(self, date):
            return {"hello": "world"}

    app = Flask(__name__)
    app.debug = True
    api = Api(app)
    api.add_resource(Hello)

    return api


def test_api_before_request():
    api = create_api()
    app = api.app

    mk = Mock(return_value={"hello": "before_request"})
    api.before_request(mk)

    with app.test_client() as c:
        assert b"before_request" in c.get("/hello", query_string={"name": "haha"}).data
        assert b"before_request" in c.get("/hello", query_string={"name": "ha!@#ha"}).data
        mk.return_value = None
        assert b"haha" in c.get("/hello", query_string={"name": "haha"}).data
        assert 400 == c.get("/hello", query_string={"name": "ha!@#ha"}).status_code


def test_api_after_request():
    api = create_api()
    app = api.app

    with app.test_client() as c:
        assert b"haha" in c.get("/hello", query_string={"name": "haha"}).data
        assert 400 == c.get("/hello", query_string={"name": "ha!@#ha"}).status_code
        mk = Mock()
        mk.return_value = ({"hello": "after_request"}, 200, None)
        api.after_request(mk)
        assert b"after_request" in c.get("/hello", query_string={"name": "haha"}).data
        assert b"after_request" in c.get("/hello", query_string={"name": "ha!@#ha"}).data


def test_befor_after():
    api = create_api()
    app = api.app

    before = Mock(return_value={"hello": "before_request"})
    api.before_request(before)

    after = Mock()
    after.return_value = ({"hello": "after_request"}, 200, None)
    api.after_request(after)

    with app.test_client() as c:
        assert b"after_request" in c.get("/hello", query_string={"name": "haha"}).data
        assert b"after_request" in c.get("/hello", query_string={"name": "ha!@#ha"}).data


def test_api_error_handler():
    api = create_api()
    app = api.app

    mk = Mock(return_value="error_handler")
    api.error_handler(mk)

    with app.test_client() as c:
        assert b"error_handler" in c.get("/hello/error").data
        mk.return_value = None
        with pytest.raises(ValueError):
            c.get("/hello/error").data


def test_base():
    api = create_api()
    app = api.app

    with app.test_client() as c:
        assert b"world" in c.get("/hello").data
        assert b"haha" in c.get("/hello", query_string={"name": "haha"}).data
        assert b"name" in c.get("/hello", query_string={"name": "ha!@#ha"}).data
