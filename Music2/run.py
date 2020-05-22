#!/usr/bin/env python
# coding:utf8

import jieba
import json
import time
from config import *
import pymysql.cursors
import pymysql
from flask import *
import warnings
import numpy as np
from collections import Counter
import re
import time
from surprise import *
import a_functions
warnings.filterwarnings("ignore")
app = Flask(__name__)
app.config.from_object(__name__)
# app.jinja_env.variable_start_string = '{{ '
# app.jinja_env.variable_end_string = ' }}'

# 连接数据库
def connectdb():
    db = pymysql.connect(host=HOST, user=USER, passwd=PASSWORD, db=DATABASE,
                         port=PORT, charset=CHARSET, cursorclass=pymysql.cursors.DictCursor)
    db.autocommit(True)
    cursor = db.cursor()
    return (db, cursor)

# 关闭数据库
def closedb(db, cursor):
    db.close()
    cursor.close()

#获得歌名到id的映射
def read_item_name():
    (db,cursor) = connectdb()
    sql='SELECT songid,songname FROM song WHERE songid IN (SELECT songid FROM user_score)'
    cursor.execute(sql)
    name_id = cursor.fetchall()
    sid_to_name = {}
    sname_to_rid = {}
    for item in name_id:
        sid_to_name[item['songid']]=item['songname']
        sname_to_rid[item['songname']] = item['songid']
    return sid_to_name,sname_to_rid
#训练模型
def get_model(user_based=False):
    #载入用户歌曲评分数据
    reader = Reader(sep=',',rating_scale=(45,100),line_format='user item rating')
    data = Dataset.load_from_file(r'C:\Users\89556\Desktop\Music\static\data\user_score.txt',reader)
    #建立训练集
    train_set = data.build_full_trainset()
    #使用pearson_baseline方式计算相似度  False以item为基准计算相似度 本例为电影之间的相似度
    sim_options = {'name':'pearson_baseline','user_based':user_based}
    #使用KNNBaseline算法
    algo = KNNWithMeans(sim_options=sim_options)
    #训练模型
    algo.train(train_set)
    print("Done model")
    return algo
algos=get_model()
# algou = get_model(True)
# id2name,name2id= read_item_name()

#基于模型做推荐
def showSimiliarSong(algo,id,number=30):
    #转换成innerId
    print('algo'+str(algo))
    print('rawid:'+str(id)+';')
    only_one_inner_id = algo.trainset.to_inner_iid(id)
    #通过模型获得推荐歌曲
    only_one_ne = algo.get_neighbors(only_one_inner_id,number)
    #转换成songId
    ne_raw_id = [algo.trainset.to_raw_iid(innerid) for innerid in only_one_ne]
    return ne_raw_id
# 首页
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/feed',methods=['POST'])
def feed():
    global algos
    data = request.data
    data = data.decode('utf-8')
    print(data)
    datas = data.split('&')
    if len(datas)>1:
        user = datas[-1].split('=')[-1]
        print("user:"+user)
        ids=[]
        for i in range(0,len(datas)-1):
            ids.append(datas[i].split('=')[-1])
        print("Data:"+str(ids))
        (db,cursor) = connectdb()
        for id in ids:
            sql = 'select * from user_score where songid=%s and userid=%s'
            cursor.execute(sql,(id,user))
            res = cursor.fetchall()
            print(res)
            sql = 'insert into user_score(userid,songid,songscore) values(%s,%s,%s)  on DUPLICATE KEY UPDATE songscore=songscore+%s'
            cursor.execute(sql,(user,id,50,5))
            sql = 'SELECT songscore FROM user_score where userid=%s and songid=%s'
            cursor.execute(sql,(user,id))
            score = cursor.fetchone()['songscore']
            info = open(r'C:\Users\89556\Desktop\Music\static\data\user_score.txt','a')
            info.write("\n"+str(user)+","+str(id)+","+str(score))
            info.close()
            algos= get_model()
    return jsonify({'msg':'success'})
@app.route('/recom', methods=['POST'])
def recom():
    global algos
    data = request.form
    user = '1346233343'
    if data['user']:
        user = data['user']
        print('user'+user)
    sql  = 'select * from user_score where userid=%s order by songscore desc'
    (db,cursor) = connectdb()
    cursor.execute(sql,(str(user)))
    ids = cursor.fetchall()
    dataStatics={}
    dataStatics['data']=[]
    flag=True
    if not ids:
        url='https://music.163.com/weapi/v1/play/record?csrf_token='
        priKey = a_functions.create_random_16()
        data = '{uid:"'+user+'",type:"-1",limit:"1000",offset:"0",total:"true",csrf_token:""}'
        params = a_functions.get_params(data,priKey)
        encSecKey = a_functions.get_encSecKey(priKey)
        data = {"params": str(params, encoding='utf-8'), "encSecKey": encSecKey}
        postinfo = a_functions.fake_browserp(url,data)
        info = json.loads(postinfo)
        if 'msg' in info:
            a_functions.exe_db(db,'insert into uuser(UserId,UserName,flag) values(%s,%s,%s) on DUPLICATE KEY UPDATE UserName=VALUES(UserName),flag=VALUES(flag)',(user,'Default','NoPermission'))
            flag=False
        else:
            alldata = info['allData']
            text = ''
            for i in range(0,len(alldata)):
                score = alldata[i]['score']
                songinf = alldata[i]['song']['song']
                songname = songinf['name']
                songid = songinf['id']
                if i == 0:
                    text = text + '\n'
                    id = songid
                text = text + str(user)+','+str(songid)+','+str(score)
                if i != len(alldata)-1:
                   text = text + '\n'
                artists = []
                for ar in songinf['artists']:
                    artist={}
                    artist['id']=ar['id']
                    artist['name']=ar['name']   
                    artists.append(artist)
                sql = 'insert into song(songid,SongName) values(%s,%s) on duplicate key update SongName=VALUES(SongName)'
                cursor.execute(sql,(songid,songname))
                a_functions.exe_db(db,'insert into uuser(UserId,UserName,flag) values(%s,%s,%s) on DUPLICATE KEY UPDATE UserName=VALUES(UserName),flag=VALUES(flag)',(user,'Default','NoPermission'))
                for a in artists:
                    a_functions.exe_db(db, 'insert into artist(ArtistId,ArtistName) values(%s,%s) on duplicate key update ArtistName=VALUES(ArtistName),',
                                       (a['id'],a['name']))
                    a_functions.exe_db(db, 'REPLACE INTO SongHasArtist(SongId,ArtistId) VALUES (%s,%s)',
                                            (songid, a['id']))
                a_functions.exe_db(db, 'replace into user_score(UserId,SongId,SongScore) values(%s,%s,%s)', (user, songid, score))
            info = open(r'C:\Users\89556\Desktop\Music\static\data\user_score.txt','a')
            info.write(text)
            info.close()
            algos= get_model()
    else:
        id=ids[0]['songid']
    if flag:
        similarid=showSimiliarSong(algo=algos,number=30,id=str(id))
    else:
        dataStatics['data']=[]
        sql = 'SELECT song.songid,count(*) count FROM song,user_score where song.songid=user_score.songid and PlayTime is not null GROUP BY song.songid  ORDER BY count DESC limit 30'
        cursor.execute(sql)
        ids = cursor.fetchall()
        similarid = []
        for i in ids:
            similarid.append(i['songid'])
    for id in similarid:
        sql = 'select songname from song where songid=%s'
        cursor.execute(sql,(id))
        da = cursor.fetchall()[0]
        sql2 = 'select artist.artistname from songhasartist,artist where songhasartist.artistid=artist.artistid and songid=%s'
        cursor.execute(sql2,(id))
        singers = cursor.fetchall()
        song={}
        song['id']=id
        song['name']=da['songname']
        song['artist']=[]
        for singer in singers:
            song['artist'].append(singer['artistname'])
        dataStatics['data'].append(song)
    dataStatics['u'] = user
    return render_template('recom.html', statics=dataStatics)
    
@app.route('/hotsongs')
def hotsongs():
    idds = []
    (db,cursor) = connectdb()
    sql = 'SELECT song.songid,count(*) count FROM song,user_score where song.songid=user_score.songid and PlayTime is not null GROUP BY song.songid  ORDER BY count DESC limit 30'
    cursor.execute(sql)
    ids = cursor.fetchall()
    for i in ids:
        idds.append(i['songid'])
    dataStatics={}
    dataStatics['data']=[]
    for id in idds:
        sql = 'select songname from song where songid=%s'
        cursor.execute(sql,(id))
        da = cursor.fetchall()[0]
        sql2 = 'select artist.artistname from songhasartist,artist where songhasartist.artistid=artist.artistid and songid=%s'
        cursor.execute(sql2,(id))
        singers = cursor.fetchall()
        song={}
        song['id']=id
        song['name']=da['songname']
        song['artist']=[]
        for singer in singers:
            song['artist'].append(singer['artistname'])
        dataStatics['data'].append(song)
    return render_template('hotsongs.html',statics=dataStatics)

@app.route('/song_comment_datedef')
def song_comment_datedef():
    id = '1300287'
    sql = "SELECT commentTime,COUNT(*) count from `comment` WHERE commentid in( SELECT commentid FROM song_comment WHERE songid=%s) GROUP BY commentTime"
    (db, cursor) = connectdb()
    cursor.execute(sql,(id))
    info = cursor.fetchall()
    dateStatics = {}
    dateStatics['data'] = []
    dateStatics['date'] = []
    for inf in info:
        date = str(inf['commentTime'])
        data = int(inf['count'])
        dateStatics['data'].append(data)
        dateStatics['date'].append(date)
    sql = 'select songname from song where songid=%s'
    cursor.execute(sql,(id))
    name = cursor.fetchall()
    if name :
        name = name[0]['songname']
        dateStatics['name']=name
    return render_template('song_comment_date.html', statics=dateStatics)

@app.route('/song_comment_date',methods=['POST'])
def song_comment_date():
    data = request.form
    id='1300287'
    if data['id']:
        id = data['id']
    sql = "SELECT commentTime,COUNT(*) count from `comment` WHERE commentid in( SELECT commentid FROM song_comment WHERE songid=%s) GROUP BY commentTime"
    (db, cursor) = connectdb()
    cursor.execute(sql,(id))
    info = cursor.fetchall()
    dateStatics = {}
    dateStatics['data'] = []
    dateStatics['date'] = []
    if info:
        for inf in info:
            date = str(inf['commentTime'])
            data = int(inf['count'])
            dateStatics['data'].append(data)
            dateStatics['date'].append(date)
    sql = 'select songname from song where songid=%s'
    cursor.execute(sql,(id))
    name = cursor.fetchall()
    if name :
        name = name[0]['songname']
        dateStatics['name']=name
    return render_template('song_comment_date.html', statics=dateStatics)


@app.route('/same_taste_user_age_rangedef')
def same_taste_user_age_rangedef():
    id = '100049561'
    sql = "SELECT Userage FROM uuser WHERE  UserID IN (SELECT distinct userid FROM user_score WHERE songId in( SELECT songId from user_score WHERE userid=%s)) and Userage is not null"
    (db, cursor) = connectdb()
    cursor.execute(sql,(id))
    ages = cursor.fetchall()
    ageStatics = {}
    ageStatics['0~10'] = 0
    ageStatics['10~50'] = 0
    ageStatics['18~25'] = 0
    ageStatics['26~40'] = 0
    ageStatics['40~59'] = 0
    ageStatics['60~'] = 0
    for age in ages:
        co = age['Userage']
        if(co != 'Unknown'):
            co = float(co)
            if co < 10:
                ageStatics['0~10'] += 1
            elif co < 18:
                ageStatics['10~50'] += 1
            elif co < 25:
                ageStatics['18~25'] += 1
            elif co < 40:
                ageStatics['26~40'] += 1
            elif co < 60:
                ageStatics['40~59'] += 1
            else:
                ageStatics['60~'] += 1
    sql = 'select username from uuser where userid=%s'
    cursor.execute(sql,(id))
    name = cursor.fetchall()
    if name:
        name=name[0]['username']
        ageStatics['name']=name
    return render_template('same_taste_user_age_range.html', statics=ageStatics)
@app.route('/same_taste_user_age_range',methods=['POST'])
def same_taste_user_age_range():
    data = request.form
    id = '100049561'
    if data['id']:
        id = data['id']
    sql = "SELECT Userage FROM uuser WHERE  UserID IN (SELECT distinct userid FROM user_score WHERE songId in( SELECT songId from user_score WHERE userid=%s)) and Userage is not null"
    (db, cursor) = connectdb()
    cursor.execute(sql,(id))
    ages = cursor.fetchall()
    ageStatics = {}
    ageStatics['0~10'] = 0
    ageStatics['10~50'] = 0
    ageStatics['18~25'] = 0
    ageStatics['26~40'] = 0
    ageStatics['40~59'] = 0
    ageStatics['60~'] = 0
    print(ages)
    for age in ages:
        co = age['Userage']
        print('Co:'+str(co))
        if(co != 'Unknown'):
            co = float(co)
            if co < 10:
                ageStatics['0~10'] += 1
            elif co < 18:
                ageStatics['10~50'] += 1
            elif co < 25:
                ageStatics['18~25'] += 1
            elif co < 40:
                ageStatics['26~40'] += 1
            elif co < 60:
                ageStatics['40~59'] += 1
            else:
                ageStatics['60~'] += 1
    sql = 'select username from uuser where userid=%s'
    cursor.execute(sql,(id))
    name = cursor.fetchall()
    if name:
        name=name[0]['username']
        ageStatics['name']=name
    return render_template('same_taste_user_age_range.html', statics=ageStatics)


@app.route('/song_user_age_rangedef')
def song_user_age_rangedef():
    id='27743746'
    sql = "SELECT Userage FROM uuser,user_comment WHERE uuser.UserID=user_comment.userId AND user_comment.commentId IN (SELECT commentId FROM song_comment WHERE songId=%s)"
    (db, cursor) = connectdb()
    cursor.execute(sql,(id))
    ages = cursor.fetchall()
    ageStatics = {}
    ageStatics['0~10'] = 0
    ageStatics['10~50'] = 0
    ageStatics['18~25'] = 0
    ageStatics['26~40'] = 0
    ageStatics['40~59'] = 0
    ageStatics['60~'] = 0
    for age in ages:
        co = age['Userage']
        if(co != 'Unknown'):
            co = float(co)
            if co < 10:
                ageStatics['0~10'] += 1
            elif co < 18:
                ageStatics['10~50'] += 1
            elif co < 25:
                ageStatics['18~25'] += 1
            elif co < 40:
                ageStatics['26~40'] += 1
            elif co < 60:
                ageStatics['40~59'] += 1
            else:
                ageStatics['60~'] += 1
    sql = 'select songname from song where songid=%s'
    cursor.execute(sql,(id))
    name = cursor.fetchall()
    if name:
        name=name[0]['songname']
        ageStatics['name']=name
    return render_template('song_user_age_range.html', statics=ageStatics)
@app.route('/song_user_age_range',methods=['POST'])
def song_user_age_range():
    data = request.form
    id = '27743746'
    if data['id']:
        id = data['id']
    sql = "SELECT Userage FROM uuser,user_comment WHERE uuser.UserID=user_comment.userId AND user_comment.commentId IN (SELECT commentId FROM song_comment WHERE songId=%s)"
    (db, cursor) = connectdb()
    cursor.execute(sql,(id))
    ages = cursor.fetchall()
    ageStatics = {}
    ageStatics['0~10'] = 0
    ageStatics['10~50'] = 0
    ageStatics['18~25'] = 0
    ageStatics['26~40'] = 0
    ageStatics['40~59'] = 0
    ageStatics['60~'] = 0
    if ages:
        for age in ages:
            co = age['Userage']
            if(co != 'Unknown'):
                co = float(co)
                if co < 10:
                    ageStatics['0~10'] += 1
                elif co < 18:
                    ageStatics['10~50'] += 1
                elif co < 25:
                    ageStatics['18~25'] += 1
                elif co < 40:
                    ageStatics['26~40'] += 1
                elif co < 60:
                    ageStatics['40~59'] += 1
                else:
                    ageStatics['60~'] += 1
    sql = 'select songname from song where songid=%s'
    cursor.execute(sql,(id))
    name = cursor.fetchall()
    if name:
        name=name[0]['songname']
        ageStatics['name']=name
    return render_template('song_user_age_range.html', statics=ageStatics)


@app.route('/song_user_area_rangedef')
def song_user_area_rangedef():
    id = '27743746'
    sql = "SELECT UserArea,count(*) count FROM uuser,user_comment WHERE uuser.UserID=user_comment.userId AND user_comment.commentId IN (SELECT commentId FROM song_comment WHERE songId='27743746') GROUP BY UserArea"
    #sql = "SELECT UserArea,COUNT(*) count FROM Uuser GROUP BY UserArea"
    (db, cursor) = connectdb()
    cursor.execute(sql)
    areas = cursor.fetchall()
    areaStatics = {}
    areaStatics['data'] = []
    maxvalue = 0
    for area in areas:
        areaName = str(area['UserArea'])
        areaCount = int(area['count'])
        if areaName != 'Unknown' and areaName != '海外':
            areaStatics['data'].append({'name': areaName, 'value': areaCount})
            maxvalue = maxvalue if maxvalue > int(
                area['count']) else int(area['count'])
    areaStatics['maxvalue'] = maxvalue
    sql = "select songname from song where songid=%s"
    cursor.execute(sql,(id))
    song = cursor.fetchall()
    if song:
        song = song[0]['songname']
        areaStatics['name']=song
    return render_template('song_user_area_range.html', statics=areaStatics)
@app.route('/song_user_area_range',methods=['POST'])
def song_user_area_range():
    data = request.form
    id='27743746'
    if data['id']:
        id=data['id']
    sql = "SELECT UserArea,count(*) count FROM uuser,user_comment WHERE uuser.UserID=user_comment.userId AND user_comment.commentId IN (SELECT commentId FROM song_comment WHERE songId=%s) GROUP BY UserArea"
    (db, cursor) = connectdb()
    cursor.execute(sql,(id))
    areas = cursor.fetchall()
    areaStatics = {}
    areaStatics['data'] = []
    maxvalue = 0
    for area in areas:
        areaName = str(area['UserArea'])
        areaCount = int(area['count'])
        if areaName != 'Unknown' and areaName != '海外':
            areaStatics['data'].append({'name': areaName, 'value': areaCount})
            maxvalue = maxvalue if maxvalue > int(
                area['count']) else int(area['count'])
    areaStatics['maxvalue'] = maxvalue
    sql = "select songname from song where songid=%s"
    cursor.execute(sql,(id))
    song = cursor.fetchall()
    if song:
        song = song[0]['songname']
        areaStatics['name']=song
    return render_template('song_user_area_range.html', statics=areaStatics)


@app.route('/tagwordcloud')
def tagwordcloud():
    sql = "SELECT stylename, count(*) count from playlisthasstyle GROUP BY playlisthasstyle.StyleName"
    (db, cursor) = connectdb()
    cursor.execute(sql)
    tags = cursor.fetchall()
    tagStatics = {}
    tagStatics['data'] = []
    for tag in tags:
        tagName = str(tag['stylename'])
        tagCount = int(tag['count'])
        tagStatics['data'].append({'name': tagName, 'value': tagCount})
    return render_template('tagwordcloud.html', statics=tagStatics)

@app.route('/commentwordclouddef')
def commentwordclouddef():
    id='28315784'
    sql = "SELECT `comment`.commentContent FROM `comment` where commentid in(Select commentid FROM song_comment WHERE songid=%s)"
    (db, cursor) = connectdb()
    cursor.execute(sql,id)
    comments = cursor.fetchall()
    content = ''
    for comment in comments:
        content += comment['commentContent'] + ' '
    #content = re.sub(
    #    "[\s+\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；\(\)《》\<\>=-\[\]\{\}我你他啊的得嗯哈了呢呐嘿哼这那没都里外内就是怎么竟然还说吧个]+", "", content)
    content = re.sub(
        "[\s+\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；\(\)《》\<\>=-\[\]\{\}]+", "", content)
    cut_content = jieba.cut(content, cut_all=False)
    content = ' '.join(cut_content)
    content = re.sub(
        "[我你他啊的得嗯哈了呢呐嘿哼这那没都里外内就是怎么竟然还说吧个]", "", content)
    contents = content.split(' ')
    statics = {}
    statics['data'] = []
    data = Counter(contents)
    for name, count in data.items():
        statics['data'].append({'name': name, 'value': count})
    sql = "select songname from song where songid=%s"
    cursor.execute(sql,(id))
    song = cursor.fetchall()
    if song:
        song = song[0]['songname']
        statics['name']=song
    return render_template('commentwordcloud.html', statics=statics)

@app.route('/commentwordcloud', methods=['POST'])
def commentwordcloud():
    data = request.form
    id='28315784'
    if data['id']:
        id=data['id']
    sql = "SELECT `comment`.commentContent FROM `comment` where commentid in(Select commentid FROM song_comment WHERE songid=%s)"
    (db, cursor) = connectdb()
    cursor.execute(sql,id)
    comments = cursor.fetchall()
    content = ''
    for comment in comments:
        content += comment['commentContent'] + ' '
    if not content:
        content="查无此项"
    #content = re.sub(
    #    "[\s+\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；\(\)《》\<\>=-\[\]\{\}我你他啊的得嗯哈了呢呐嘿哼这那没都里外内就是怎么竟然还说吧个]+", "", content)
    content = re.sub(
        "[\s+\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：；\(\)《》\<\>=-\[\]\{\}]+", "", content)
    cut_content = jieba.cut(content, cut_all=False)
    content = ' '.join(cut_content)
    content = re.sub(
        "[我你他啊的得嗯哈了呢呐嘿哼这那没都里外内就是怎么竟然还说吧个]", "", content)
    contents = content.split(' ')
    statics = {}
    statics['data'] = []
    data = Counter(contents)
    for name, count in data.items():
        statics['data'].append({'name': name, 'value': count})
    sql = "select songname from song where songid=%s"
    cursor.execute(sql,(id))
    song = cursor.fetchall()
    if song:
        song = song[0]['songname']
        statics['name']=song
    return render_template('commentwordcloud.html', statics=statics)

@app.route('/commentlikedrangedef')
def commentlikedrangedef():
    id='28315784'
    sql = "SELECT commentid,`comment`.likedCount lik FROM `comment` WHERE commentid in  (SELECT commentid FROM song_comment WHERE songid=%s)"
    (db, cursor) = connectdb()
    cursor.execute(sql,id)
    coms = cursor.fetchall()
    comStatics = {}
    comStatics['0~10'] = 0
    comStatics['10~50'] = 0
    comStatics['50~100'] = 0
    comStatics['100~200'] = 0
    comStatics['200~1000'] = 0
    comStatics['1000~'] = 0
    for com in coms:
        co = com['lik']
        co = float(co)
        if co < 10:
            comStatics['0~10'] += 1
        elif co < 50:
            comStatics['10~50'] += 1
        elif co < 100:
            comStatics['50~100'] += 1
        elif co < 200:
            comStatics['100~200'] += 1
        elif co < 1000:
            comStatics['200~1000'] += 1
        else:
            comStatics['1000~'] += 1
    sql = "select songname from song where songid=%s"
    cursor.execute(sql,(id))
    song = cursor.fetchall()
    if song:
        song = song[0]['songname']
        comStatics['name']=song
    return render_template('commentlikedrange.html', statics=comStatics)

@app.route('/commentlikedrange', methods=['POST'])
def commentlikedrange():
    data = request.form
    id='28315784'
    if data['id']:
        id=data['id']
    sql = "SELECT commentid,`comment`.likedCount lik FROM `comment` WHERE commentid in  (SELECT commentid FROM song_comment WHERE songid=%s)"
    (db, cursor) = connectdb()
    cursor.execute(sql,id)
    coms = cursor.fetchall()
    comStatics = {}
    comStatics['0~10'] = 0
    comStatics['10~50'] = 0
    comStatics['50~100'] = 0
    comStatics['100~200'] = 0
    comStatics['200~1000'] = 0
    comStatics['1000~'] = 0
    for com in coms:
        co = com['lik']
        co = int(co)
        if co < 10:
            comStatics['0~10'] += 1
        elif co < 50:
            comStatics['10~50'] += 1
        elif co < 100:
            comStatics['50~100'] += 1
        elif co < 200:
            comStatics['100~200'] += 1
        elif co < 1000:
            comStatics['200~1000'] += 1
        else:
            comStatics['1000~'] += 1
    sql = "select songname from song where songid=%s"
    cursor.execute(sql,(id))
    song = cursor.fetchall()
    if song:
        song = song[0]['songname']
        comStatics['name']=song
    return render_template('commentlikedrange.html', statics=comStatics)


@app.route('/songstatics')
def songstatics():
    sql='SELECT songname,PlayTime,PubTime,count(*) count FROM song,user_score where song.songid=user_score.songid and PlayTime is not null GROUP BY song.songid  ORDER BY count DESC limit 500'   
    (db, cursor) = connectdb()
    cursor.execute(sql)
    datas = cursor.fetchall()
    statics = {}
    statics['data']=[]
    maxvalue = 0
    maxplaytime=0
    for data in datas:
        statics['data'].append([data['PlayTime']/1000,data['PubTime'],data['count']])
        maxvalue = maxvalue if maxvalue > int(
                data['count']) else int(data['count'])
        maxplaytime = maxplaytime if maxplaytime >int(data['PlayTime']/1000)else int(data['PlayTime']/1000)
    statics['maxvalue'] = maxvalue
    statics['maxplaytime'] = maxplaytime
    return render_template('songstatics.html',data=statics)


if __name__ == '__main__':
    app.run(debug=True)
