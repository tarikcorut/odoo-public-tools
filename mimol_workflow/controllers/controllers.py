# -*- coding: utf-8 -*-
# from odoo import http


# class Con(http.Controller):
#     @http.route('/con/con', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/con/con/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('con.listing', {
#             'root': '/con/con',
#             'objects': http.request.env['con.con'].search([]),
#         })

#     @http.route('/con/con/objects/<model("con.con"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('con.object', {
#             'object': obj
#         })
