#
# Copyright (C) 2011 Radicore AB.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
# Author: Lars Sjostrom <lars@radicore.se>

import web
import os
import sys
try:
    sys.path.append(os.path.dirname(__file__))
except:
    pass
import model

template_root = os.path.join(os.path.dirname(__file__), "templates/")
render = web.template.render(template_root, base='base', cache=False)

# web.webapi.internalerror = web.debugerror #lets capture errors for debugging
web.config.debug = False

urls = (
    '/', 'Index',
    '/new', 'New',
    '/login', 'Login',
    '/logout', 'Logout',
    '/edit/(\w+)', 'Edit',
    '/delete/(\w+)', 'Delete'
    )

# this is the main from the PythonOption wsgi.application controller::main
app = web.application(urls, globals())
application = app.wsgifunc()

session_root =  os.path.join(os.path.dirname(__file__), "sessions")

if web.config.get('_session') is None:
    session = web.session.Session(app, web.session.DiskStore(session_root), initializer={'token': None})
    web.config._session = session
    session.token = None
else:
    session = web.config._session
    session.token = None

def system_form():
    return web.form.Form( 
        web.form.Hidden('name'), 

        web.form.Textbox('hostname',
                         web.form.regexp("^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*$",'Invalid'),
                         web.form.notnull, size="36", 
                         description="Hostname (FQDN)"), 
        
        web.form.Hidden('adv_networks', 
                        pre='<label for="advnet"><a href="#">Advanced Networking</a></label><div id="adv_network">'),
        
        web.form.Textbox('mac_address', 
                         web.form.regexp('^\s*$|([a-fA-F0-9]{2}[:]?){6}','Invalid'), 
                         post='<p/>', size="36", maxlength="17", 
                         description="Mac Address (Optional)"), 
        
        web.form.Checkbox('bonding', id="bonding", value="bonding", 
                          post='<p/><div id="bond">', description="Enable Bonding "), 
        
        web.form.Dropdown('eth_name1', ['eth0','eth1','eth2','eth3'], 
                          description="Interface "), 
        
        web.form.Textbox('mac_addr1', 
                         web.form.regexp('^\s*$|([a-fA-F0-9]{2}[:]?){6}','Invalid'), 
                         size="17", maxlength="17", post="<p/>", description="Mac "), 
        
        web.form.Dropdown('eth_name2', ['eth0','eth1','eth2','eth3'], value="eth1", 
                          description="Interface "), 
        
        web.form.Textbox('mac_addr2', 
            web.form.regexp('^\s*$|([a-fA-F0-9]{2}[:]?){6}','Invalid'), 
            size="17", maxlength="17", post="<p/>", description="Mac "), 
        
        web.form.Textbox('bonding_opts', size="36", post="</div></div>", 
                         description="Bonding Options", value="mode=1 miimon=100"), 
        
        web.form.Textbox('ip_address',
            web.form.notnull, 
            web.form.Validator('Invalid', lambda i: web.net.validipaddr(i)), 
            size="36", description="IP Address"),
        
        web.form.Textbox('subnet',
            web.form.notnull,
            web.form.Validator('Invalid', lambda i: web.net.validipaddr(i)), 
            size="36", description="Netmask"), 
        
        web.form.Textbox('gateway',
            web.form.notnull,
            web.form.Validator('Invalid', lambda i: web.net.validipaddr(i)), 
            size="36", description="Gateway"), 
        
        web.form.Textbox('name_servers',
            web.form.Validator('Invalid', lambda i: web.net.validipaddr(i.split()[0])), 
            web.form.notnull, size="36", description="Name Servers"), 
        
        web.form.Textbox('name_servers_search', web.form.notnull, size="36", 
                         description="Domain Search"), 
        
        web.form.Dropdown('profile', model.get_profiles(), 
                          description="Kickstart Profile"),
        
        web.form.Textbox('redhat_management_key', size="36", 
                         description="Activation Keys (Optional)")
     ) 

class Login:

    login_form = web.form.Form(web.form.Textbox('username',
                                     description='Username:'),
                                web.form.Password('password',
                                     description='Password:'),
                                validators = [web.form.Validator("Username and password didn't match.",
                                     lambda x: model.get_token(x.username,x.password)) ])
    def GET(self):
        if session.token:
            raise web.seeother('/')

        form = self.login_form()
        return render.login(form)

    def POST(self):
        form = self.login_form()
        if not form.validates():
            return render.login(form)

        session.token = model.get_token(form['username'].value, form['password'].value)
        raise web.seeother('/')

class Logout:

    def GET(self):
        session.token = None
        session.kill() 
        raise web.seeother('/login')

class Index:

    def GET(self):
        if not model.test_token(session.token):
            raise web.seeother('/logout')
        systems = model.get_systems()
        return render.index(sorted(systems))

    def POST(self): 
        if not model.test_token(session.token):
            raise web.seeother('/logout')
        data = web.input(sys=[])

        if data.sys:
            file = model.generate_iso(",".join(data.sys), session.token)
            if file != None:
                web.header("Content-Disposition", "attachment; filename=generated.iso")
                web.header("Content-Type", "application/octet-stream") 
                f = open(file,"rb")
                os.unlink(file)            
		return f
        raise web.seeother('/')

class New:

    def GET(self):
        if not model.test_token(session.token):
            raise web.seeother('/logout')
        form = system_form()
        return render.new(form)

    def POST(self):
        if not model.test_token(session.token):
            raise web.seeother('/logout')
        form = system_form()
        if not form.validates():
            return render.new(form)
        s = model.crud_system(form, session.token)
        if s:
            return render.new(form, s)
        raise web.seeother('/')

class Edit:

    def GET(self, uid):
        if not model.test_token(session.token):
            raise web.seeother('/logout')
        system = model.get_formdata_by_uid(uid)
        if system == None:
            raise web.seeother('/')
        form = system_form()
        form.fill(system)
        return render.edit(form, uid) 

    def POST(self, uid):
        if not model.test_token(session.token):
            raise web.seeother('/logout')
        form = system_form()
        if not form.validates():
            return render.edit(form, uid)
        s = model.crud_system(form, session.token)
        if s:
            return render.edit(form, uid, s)
        raise web.seeother('/')

class Delete:

    def POST(self,uid):
        if not model.test_token(session.token):
            raise web.seeother('/logout')
        model.remove_system(uid, session.token)
        raise web.seeother('/')
        

if __name__=="__main__":
    app.run()
