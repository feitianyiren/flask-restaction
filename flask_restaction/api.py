# coding:utf-8

from flask import Blueprint, request
import os
from os.path import join, exists
import jwt
from jinja2 import Template
from . import Permission
from . import pattern_action
from . import abort
from . import res_js


class Api(object):

    """Api

    :param app: Flask or Blueprint
    :param permission_path: permission file path
    :param auth_header: httpheader name
    :param auth_secret: jwt secret
    :param auth_algorithm: jwt algorithm
    :param resjs_name: res.js file name
    """

    def __init__(self, app=None, permission_path="permission.json",
                 auth_header="Authorization", auth_secret="SECRET",
                 auth_algorithm="HS256", resjs_name="res.js"):
        self.permission_path = permission_path
        self.auth_header = auth_header
        self.auth_secret = auth_secret
        self.auth_algorithm = auth_algorithm
        self.resjs_name = resjs_name

        self.resources = []

        self.before_request_funcs = []
        self.after_request_funcs = []
        self.handle_error_func = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """init_app"""
        self.app = app
        if self.is_blueprint():
            self.app.record(lambda s: self.init_permission(s.app))
        else:
            self.init_permission(app)

    def init_permission(self, app):
        """init_permission

        :param app: Flask or Blueprint
        """
        ppath = join(app.root_path, self.permission_path)
        if exists(ppath):
            self.permission_path = ppath
            self.permission = Permission(filepath=ppath)
        else:
            self.permission = Permission()
            # allow all request
            self.permission.add("*", "*", None)

    def is_blueprint(self):
        """is_blueprint"""
        return isinstance(self.app, Blueprint)

    def parse_resource(self, res_cls, name=None):
        """parse_resource

        :param res_cls: resource class
        :param name: display resource name
        """
        if not type(res_cls) is type:
            raise ValueError("%s is not class" % res_cls)
        classname = res_cls.__name__.lower()
        if name is None:
            name = classname
        else:
            name = name.lower()
        meth_act = [tuple(pattern_action.findall(x)[0]) for x in dir(res_cls)
                    if pattern_action.match(x)]
        actions = []
        for meth, act in meth_act:
            if act == "":
                action = meth
                url = "/" + name
                endpoint = name
            else:
                action = meth + "_" + act
                url = "/{0}/{1}".format(name, act)
                endpoint = "{0}@{1}".format(classname, act)
            actions.append((meth, act, url, endpoint, action))

        methods = set([x[0] for x in actions])
        rules = set([(x[2], x[3]) for x in actions])
        return {
            "name": name,
            "classname": classname,
            "meth_act": meth_act,
            "actions": actions,
            "methods": methods,
            "rules": rules,
        }

    def add_resource(self, res_cls, name=None, *class_args, **class_kwargs):
        """add_resource

        :param res_cls: resource class
        :param name: name
        :param class_args: class_args
        :param class_kwargs: class_kwargs
        """
        res = self.parse_resource(res_cls, name)
        res_cls.before_request_funcs.insert(0, self._before_request)
        res_cls.after_request_funcs.append(self._after_request)

        def view(*args, **kwargs):
            try:
                fn = res_cls.as_view(res["name"], *class_args, **class_kwargs)
                return fn(*args, **kwargs)
            except Exception as ex:
                if self.handle_error_func:
                    rv = self.handle_error_func(ex)
                    if rv is not None:
                        return rv
                raise

        for url, end in res["rules"]:
            self.app.add_url_rule(url, end, view, methods=res["methods"])
        self.resources.append(res)

    def gen_resjs(self):
        """生成 res.js
        """
        template = Template(res_js)
        reslist = []
        for res in self.resources:
            actions = []
            reslist.append((res["name"], self.auth_header, actions))
            for meth, act, url, endpoint, action in res["actions"]:
                needtoken = not self.permission.permit("*", res["name"], action)
                actions.append((url, meth, action, needtoken))
        js = template.render(reslist=reslist)
        if not exists(self.app.static_folder):
            os.makedirs(self.app.static_folder)
        path = join(self.app.static_folder, self.resjs_name)
        with open(path, "w") as f:
            f.write(js.encode("utf-8"))

    def parse_me(self):
        """id and role must in the token"""
        token = request.headers.get(self.auth_header)
        if token is not None:
            try:
                me = jwt.decode(token, self.auth_secret,
                                algorithms=[self.auth_algorithm])
                if "id" in me and "role" in me:
                    return me
            except Exception:
                pass
        return {"id": None, "role": "*"}

    def gen_token(self, me):
        """gen_token"""
        token = jwt.encode(me, self.auth_secret, algorithm=self.auth_algorithm)
        return token

    def _before_request(self):
        """before_request"""
        request.me = self.parse_me()
        for fn in self.before_request_funcs:
            rv = fn()
            if rv is not None:
                return rv
        if not self.permission.permit(
                request.me["role"], request.resource, request.action):
            abort(403, "permission deny")
        return None

    def _after_request(self, rv, code, headers):
        """after_request"""
        for fn in self.after_request_funcs:
            rv, code, headers = fn(rv, code, headers)
        return rv, code, headers

    def after_request(self, f):
        """装饰器"""
        self.after_request_funcs.append(f)
        return f

    def before_request(self, f):
        """装饰器"""
        self.before_request_funcs.append(f)
        return f

    def error_handler(self, f):
        """装饰器"""
        self.handle_error_func = f
        return f
