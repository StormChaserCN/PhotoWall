# coding=utf-8
import base64
import hashlib
import io
import time

import flask
import gridfs
import pymongo
from PIL import Image

app = flask.Flask(__name__)
db = None


class DBUtil(object):
    db_host = '192.168.175.129'
    db_port = 27017

    def __init__(self):
        self.client = pymongo.MongoClient(self.db_host, self.db_port)
        self.fs = gridfs.GridFS(self.client.zdb, 'imgs')
        self.t_imgs = self.client.zdb.images

    def save_file(self, data, filename, mime):
        hashname = getsha256(data)
        dbfile = self.t_imgs.find_one({'hashname': hashname})
        if dbfile is None:
            time_now = time.strftime("%Y%m%d%H%M%S", time.localtime())
            thumbdata = make_thumb(data)
            if thumbdata is not None:
                thumbhash = getsha256(thumbdata)

                try:
                    fileid = self.fs.put(data, filename=hashname)
                except:
                    return
                try:
                    thumbid = self.fs.put(thumbdata, filename=thumbhash)
                except:
                    self.fs.delete(fileid)
                    return
                try:
                    self.t_imgs.insert({'filename': filename, 'hashname': hashname, 'uploadtime': time_now, 'mime': mime,
                                        'thumbname': thumbhash, 'fileid': fileid, 'thumbid': thumbid})
                except:
                    self.fs.delete(fileid)
                    self.fs.delete(thumbid)

    def get_file(self, filename):
        a_file = self.t_imgs.find_one({'hashname': filename})
        f = self.fs.get(a_file['fileid'])
        if f is None:
            return None
        return [{'name': a_file['filename'], 'data': base64.b64encode(f.read())}]

    def list_file(self):
        files = []
        for a_file in self.t_imgs.find():
            try:
                f = self.fs.get(a_file['thumbid'])
            except:
                continue
            if f is None:
                return None
            files.append({'name': a_file['hashname'], 'data': base64.b64encode(f.read())})
        return files

    def del_file(self, filename):
        a_file = self.t_imgs.find_one({'hashname': filename})
        self.fs.delete(a_file['fileid'])
        self.fs.delete(a_file['thumbid'])
        self.t_imgs.delete_one({'fileid': a_file['fileid'], 'thumbid': a_file['fileid']})



def getsha256(data):
    h = hashlib.sha256()
    bi = io.BytesIO(data)
    CHUNK_SIZE = 102400
    while True:
        chunk = bi.read(CHUNK_SIZE)
        h.update(chunk)
        if len(chunk) != CHUNK_SIZE:
            break
    return h.hexdigest().upper()


def make_thumb(data):
    try:
        im = Image.open(io.BytesIO(data))
    except IOError:
        return None
    mode = im.mode
    if mode not in ('L', 'RGB'):
        if mode == 'RGBA':
            im.load()
            alpha = im.split()[3]
            bgmask = alpha.point(lambda x: 255 - x)
            im = im.convert('RGB')
            im.paste((255, 255, 255), None, bgmask)
        else:
            im = im.convert('RGB')
    width, height = im.size
    if width > height:
        new_width = 200
        new_hight = height * new_width / width
    elif height > width:
        new_hight = 200
        new_width = new_hight * width / height
    else:
        new_hight = new_width = 200
    thumb = im.resize((new_width, new_hight), Image.ANTIALIAS)
    bo = io.BytesIO()
    thumb.save(bo, im.format)
    bo.seek(0)
    return bo.read()


def save_file(f, filename):
    data = f.read()
    ext_list = ['jpeg', 'gif', 'png']
    try:
        im = Image.open(io.BytesIO(data))
        ext = im.format.lower()
    except:
        return
    if ext not in ext_list:
        return
    db.save_file(data, filename, ext)


@app.route('/')
def index():
    photolist = db.list_file()
    return flask.render_template('index.html', photos=photolist)


@app.route('/view')
def view():
    filename = flask.request.args['url']
    a_file = db.get_file(filename)
    return flask.render_template('view.html', img_stream=a_file[0]['data'])


@app.route('/doUpload', methods=['POST'])
def doUpload():
    try:
        f = flask.request.files['upload_img']
        save_file(f, f.filename)
    except:
        pass
    return flask.redirect('/')


@app.route('/upload')
def upload():
    return flask.render_template('upload.html')


if __name__ == '__main__':
    db = DBUtil()

    # init
    # db.t_imgs.delete_many({})
    # for i in db.fs.find():
    #     db.fs.delete(i.__getattribute__('_id'))

    app.run()
