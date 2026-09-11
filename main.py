import json, os, time, re
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

BASE = os.path.dirname(__file__)
DATA_FILE = os.path.join(BASE, "data", "day_data.json")
CONFIG_FILE = os.path.join(BASE, "firebase_config.json")

KV = '''
BoxLayout:
    orientation: "vertical"
    padding: dp(10)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: .035,.055,.09,1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        size_hint_y: None
        height: dp(58)
        Label:
            text: "⚔️ CoC COMMAND CENTER"
            font_size: "20sp"
            bold: True
            color: .96,.68,.12,1
        Button:
            text: "☁ SYNC"
            size_hint_x: None
            width: dp(90)
            on_release: app.sync_now()
        Button:
            text: "⚙"
            size_hint_x: None
            width: dp(52)
            on_release: app.open_accounts()
    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(5)
        Button:
            text: "HOME"
            on_release: app.show("home")
        Button:
            text: "RUNNING"
            on_release: app.show("running")
        Button:
            text: "COMPLETED"
            on_release: app.show("completed")
        Button:
            text: "DATABASE"
            on_release: app.show("database")
    Label:
        id: account_label
        size_hint_y: None
        height: dp(35)
        text: "Account: " + app.active_account
        color: .85,.88,.95,1
        halign: "left"
    ScrollView:
        do_scroll_x: False
        GridLayout:
            id: content
            cols: 1
            spacing: dp(8)
            padding: dp(2)
            size_hint_y: None
            height: self.minimum_height
    Button:
        text: "+ START UPGRADE"
        size_hint_y: None
        height: dp(52)
        background_normal: ""
        background_color: .95,.55,.05,1
        color: .05,.05,.05,1
        bold: True
        on_release: app.open_upgrade_form()
'''

class CocApp(App):
    def build(self):
        self.title = "CoC Command Center"
        self.logged_in = False
        self.firebase = None
        self.store = JsonStore(os.path.join(self.user_data_dir, "coc_data.json"))
        if not self.store.exists("data"):
            self.store.put("data", accounts=["Main"], active="Main", upgrades=[], history=[], modified_at=time.time())
        self.active_account = self.store.get("data")["active"]
        with open(DATA_FILE, encoding="utf-8") as f:
            self.db = json.load(f)
        from kivy.lang import Builder
        root = Builder.load_string(KV)
        Clock.schedule_interval(self.tick, 1)
        Clock.schedule_interval(self.background_sync, 20)
        Clock.schedule_once(lambda *_: self.open_login(), .3)
        Clock.schedule_once(lambda *_: self.show("home"), 0)
        return root

    def data(self): return self.store.get("data")
    def save(self, d, mark=True):
        if mark: d["modified_at"] = time.time()
        self.store.put("data", **d); self.active_account=d["active"]

    def show(self, page):
        if not self.logged_in:
            self.open_login(); return
        c=self.root.ids.content; c.clear_widgets(); d=self.data()
        self.root.ids.account_label.text=f"Account: {self.active_account}  •  ☁ {self.firebase.uid[-6:] if self.firebase and self.firebase.uid else 'offline'}"
        if page=="home":
            self.label("⚔️ ACTIVE ACCOUNT",22)
            r=[u for u in d["upgrades"] if u["account"]==self.active_account and not u["done"]]
            h=[u for u in d["history"] if u["account"]==self.active_account]
            self.label(f"{self.active_account}  •  {len(r)} running",20)
            self.label(f"Completed upgrades: {len(h)}",18)
            self.label("Maximum 5 running upgrades per account",15)
            for u in r: self.label(f"⏱ {u['item']}  •  Lv {u['level']}  •  {self.fmt(max(0,u['end']-time.time()))}",16)
        elif page in ("running","completed"):
            if page=="running":
                items=[u for u in d["upgrades"] if u["account"]==self.active_account and not u["done"]]; title="⏱️ RUNNING UPGRADES"
            else:
                items=[u for u in d["history"] if u["account"]==self.active_account]; title="✅ COMPLETED UPGRADES"
            self.label(title,20)
            if not items:self.label("No upgrades here.",17)
            for u in items:
                if page=="running": self.label(f"{u['item']}  •  Level {u['level']}  •  {self.fmt(max(0,u['end']-time.time()))}",17)
                else:self.label(f"✓ {u['item']}  •  Level {u['level']}  •  {u.get('cost','—')}",17)
        else:
            self.label("🏰 UPGRADE DATABASE",21)
            self.label(f"{len(self.db)} items loaded from the supplied CoC data PDF",15)
            for item, levels in self.db.items(): self.label(f"{item}  •  {len(levels)} levels",16)

    def label(self,text,size=16):
        w=Label(text=text,font_size=f"{size}sp",size_hint_y=None,height=dp(44),color=(.88,.9,.95,1),halign="left",valign="middle")
        w.text_size=(None,None); self.root.ids.content.add_widget(w)

    def fmt(self,sec):
        sec=int(sec); d,sec=divmod(sec,86400); h,sec=divmod(sec,3600); m,s=divmod(sec,60)
        return (f"{d}d " if d else "")+(f"{h}h " if h else "")+f"{m:02d}:{s:02d}"

    def parse_duration(self,x):
        if not x or x in ('—','-'): return 0
        total=0
        for n,u in re.findall(r'(\d+)\s*(d|h|m|s)',x.lower()): total += int(n)*{'d':86400,'h':3600,'m':60,'s':1}[u]
        return total

    # ---------- Firebase login / sync ----------
    def open_login(self):
        if self.logged_in: return
        if not os.path.exists(CONFIG_FILE): return self.popup('Firebase', 'firebase_config.json is missing.')
        try:
            from firebase_sync import FirebaseSync
            self.firebase = FirebaseSync(CONFIG_FILE)
        except Exception as e: return self.popup('Firebase', str(e))
        if not self.firebase.ready:
            return self.popup('Firebase setup needed', 'First add your Firebase Web App API key and Realtime Database URL in firebase_config.json. I will guide you one-by-one.')
        box=BoxLayout(orientation='vertical',spacing=dp(8),padding=dp(10))
        email=TextInput(hint_text='Login ID / Email',multiline=False)
        password=TextInput(hint_text='Password (6+ characters)',password=True,multiline=False)
        login=Button(text='LOGIN',size_hint_y=None,height=dp(48)); create=Button(text='CREATE LOGIN ID',size_hint_y=None,height=dp(48))
        box.add_widget(Label(text='☁ Cloud Login',size_hint_y=None,height=dp(38)));box.add_widget(email);box.add_widget(password);box.add_widget(login);box.add_widget(create)
        p=Popup(title='CoC Cloud Login',content=box,size_hint=(.94,.62),auto_dismiss=False)
        def done(kind):
            try:
                if kind=='login': self.firebase.login(email.text.strip(),password.text)
                else: self.firebase.signup(email.text.strip(),password.text)
                self.logged_in=True; p.dismiss(); self.sync_now(initial=True); self.show('home')
            except Exception as e: self.popup('Login error', str(e))
        login.bind(on_release=lambda *_:done('login')); create.bind(on_release=lambda *_:done('create')); p.open()

    def sync_now(self, initial=False):
        if not self.logged_in or not self.firebase: return
        try:
            remote=self.firebase.cloud_get(); local=self.data()
            if not remote:
                self.firebase.cloud_put(local); msg='Local data uploaded to cloud.'
            else:
                rt=float(remote.get('modified_at',0)); lt=float(local.get('modified_at',0))
                if rt > lt:
                    self.store.put('data', **remote); self.active_account=remote['active']; msg='Cloud data downloaded.'
                elif lt > rt:
                    self.firebase.cloud_put(local); msg='Local data uploaded.'
                else: msg='Already synced.'
            if not initial: self.popup('☁ Sync',msg)
            self.show('home')
        except Exception as e:
            self.popup('Sync error', str(e))

    def background_sync(self,*_):
        if self.logged_in: self.sync_now(initial=True)

    # ---------- timers ----------
    def tick(self,*_):
        d=self.data(); changed=False
        for u in d["upgrades"]:
            if not u["done"] and u["end"]<=time.time():
                u["done"]=True; d["history"].append(u.copy()); changed=True
        if changed:self.save(d)
        if self.root: self.root.ids.account_label.text=f"Account: {self.active_account}"

    def open_upgrade_form(self):
        if not self.logged_in: return self.open_login()
        d=self.data(); running=sum(1 for u in d['upgrades'] if u['account']==self.active_account and not u['done'])
        if running>=5:return self.popup("Limit", "This account already has 5 running upgrades.")
        items=sorted(self.db.keys()); box=BoxLayout(orientation='vertical',spacing=dp(8),padding=dp(10))
        item=Spinner(text=items[0],values=items,size_hint_y=None,height=dp(48)); level=Spinner(text=list(self.db[items[0]].keys())[0],values=tuple(self.db[items[0]].keys()),size_hint_y=None,height=dp(48))
        info=Label(text='',size_hint_y=None,height=dp(70)); start=Button(text='START UPGRADE',size_hint_y=None,height=dp(50))
        box.add_widget(Label(text='Item',size_hint_y=None,height=dp(28)));box.add_widget(item);box.add_widget(Label(text='Level',size_hint_y=None,height=dp(28)));box.add_widget(level);box.add_widget(info);box.add_widget(start)
        p=Popup(title='Start Upgrade',content=box,size_hint=(.92,.72))
        def refresh(*_):
            vals=tuple(self.db[item.text].keys()); level.values=vals
            if level.text not in vals: level.text=vals[0]
            row=self.db[item.text][level.text]; info.text=f"Cost: {row['cost']}\nUpgrade Time: {row['time']}"
        item.bind(text=refresh);level.bind(text=refresh);refresh()
        def go(_):
            row=self.db[item.text][level.text]; secs=self.parse_duration(row['time'])
            u={'account':self.active_account,'item':item.text,'level':level.text,'cost':row['cost'],'upgrade_time':row['time'],'start':time.time(),'end':time.time()+secs,'done':False}
            d=self.data();d['upgrades'].append(u);self.save(d);p.dismiss();self.show('running');self.sync_now(initial=True)
        start.bind(on_release=go);p.open()

    # ---------- accounts ----------
    def open_accounts(self):
        if not self.logged_in: return self.open_login()
        d=self.data();box=BoxLayout(orientation='vertical',spacing=dp(6),padding=dp(8))
        for a in d['accounts']:
            row=BoxLayout(size_hint_y=None,height=dp(45),spacing=dp(4));b=Button(text=('✓ ' if a==self.active_account else '')+a);b.bind(on_release=lambda _,n=a:self.select(n,p))
            e=Button(text='Edit',size_hint_x=.25);e.bind(on_release=lambda _,n=a:self.edit_account(n,p));x=Button(text='×',size_hint_x=.18);x.bind(on_release=lambda _,n=a:self.delete_account(n,p))
            row.add_widget(b);row.add_widget(e);row.add_widget(x);box.add_widget(row)
        add=Button(text='+ Add Account',size_hint_y=None,height=dp(48));add.bind(on_release=lambda *_:self.add_account(p));box.add_widget(add)
        p=Popup(title='Accounts',content=box,size_hint=(.94,.8));p.open()
    def select(self,name,p):d=self.data();d['active']=name;self.save(d);p.dismiss();self.show('home');self.sync_now(initial=True)
    def add_account(self,parent):self.account_dialog('',parent,False)
    def edit_account(self,name,parent):self.account_dialog(name,parent,True)
    def account_dialog(self,old,parent,editing):
        box=BoxLayout(orientation='vertical',spacing=dp(8),padding=dp(8));ti=TextInput(text=old,hint_text='Account name',multiline=False);b=Button(text='SAVE',size_hint_y=None,height=dp(48));box.add_widget(ti);box.add_widget(b)
        p=Popup(title='Edit Account' if editing else 'New Account',content=box,size_hint=(.9,.4))
        def save(_):
            name=ti.text.strip();d=self.data()
            if not name:return
            if editing and old in d['accounts']:
                if name!=old and name in d['accounts']:return
                d['accounts'][d['accounts'].index(old)]=name
                for u in d['upgrades']+d['history']:
                    if u['account']==old:u['account']=name
                if d['active']==old:d['active']=name
            elif name not in d['accounts']:d['accounts'].append(name);d['active']=name
            self.save(d);p.dismiss();parent.dismiss();self.show('home');self.sync_now(initial=True)
        b.bind(on_release=save);p.open()
    def delete_account(self,name,parent):
        d=self.data()
        if len(d['accounts'])<=1:return self.popup('Account','At least one account is required.')
        d['accounts'].remove(name);d['upgrades']=[u for u in d['upgrades'] if u['account']!=name];d['history']=[u for u in d['history'] if u['account']!=name]
        if d['active']==name:d['active']=d['accounts'][0]
        self.save(d);parent.dismiss();self.show('home');self.sync_now(initial=True)
    def popup(self,title,msg):Popup(title=title,content=Button(text=msg),size_hint=(.88,.4)).open()

if __name__=='__main__': CocApp().run()
