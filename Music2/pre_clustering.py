#!/usr/bin/env python
# coding:utf8

from config import *
import numpy as np
import os
import pandas as pds
import pymysql
import pymysql.cursors
from sklearn.cluster import KMeans
import time

ROOT_PATH = r'C:\Users\89556\Desktop\Music2\Music2'
STYLE_DICT_NAME = 'styledict.txt'
USER_DICT_NAME = 'userdict.txt'
RAW_RECORD_NAME = 'rawrecord.txt'
CLUSTER_RESULT_NAME = 'cluster_result.txt'
CLUSTER_NUM = 10
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

def getstyledict():
    sql = 'SELECT DISTINCT StyleName FROM playlisthasstyle'
    (db,cursor) = connectdb()
    cursor.execute(sql)
    ids = cursor.fetchall()
    # print(ids)
    style_names = [item['StyleName'] for item in ids]
    style_dict = {style_name: style_num for style_name, style_num in zip(style_names,range(len(ids)))}

    with open(os.path.join(ROOT_PATH, STYLE_DICT_NAME),'w',encoding='utf-8') as f:
    	for items in style_dict:
    		f.write(str(items) + '\t' + str(style_dict[items]) + '\n')

    return style_dict


def getuserdict():
    sql = 'SELECT DISTINCT UserId FROM user_score'
    (db,cursor) = connectdb()
    cursor.execute(sql)
    ids = cursor.fetchall()
    # print(ids)
    user_ids = [item['UserId'] for item in ids]
    user_dict = {user_name: user_num for user_name, user_num in zip(user_ids,range(len(ids)))}

    with open(os.path.join(ROOT_PATH, USER_DICT_NAME),'w',encoding='utf-8') as f:
        for items in user_dict:
            f.write(str(items) + '\t' + str(user_dict[items]) + '\n')
    return user_dict

def getrawrecord():
    sql = 'SELECT userId, StyleName, count(*) as Cnt FROM playlisthassong, playlisthasstyle, user_score WHERE playlisthassong.PlaylistID = playlisthasstyle.PlaylistID AND user_score.songid = playlisthassong.SongID GROUP BY userId, StyleName'
    (db,cursor) = connectdb()
    cursor.execute(sql)
    ids = cursor.fetchall()
    # print(ids)

    raw_record = [(items['userId'], items['StyleName'], items['Cnt']) for items in ids]

    with open(os.path.join(ROOT_PATH, RAW_RECORD_NAME),'w',encoding='utf-8') as f:
        for items in raw_record:
        	f.write(items[0] + '\t' + items[1] + '\t' + str(items[2]) + '\n')

    return raw_record

def getfeaturematrix(user_dict, style_dict, raw_record):
    matrix = np.zeros((len(user_dict), len(style_dict)), dtype = np.float)

    for items in raw_record:
        matrix[user_dict[items[0]], style_dict[items[1]]] = items[2]

    return matrix

def getclusterresult(user_dict, matrix, model):
    cluster_result = {}
    
    model_result = model.fit(matrix)
    labels = model_result.labels_
    new_dict = {v:k for k,v in user_dict.items()}
    for i in range(len(user_dict)):
        cluster_result[new_dict[i]] = int(labels[i])

    with open(os.path.join(ROOT_PATH, CLUSTER_RESULT_NAME),'w',encoding='utf-8') as f:
        for items in cluster_result:
            f.write(items + '\t' + str(cluster_result[items]) + '\n')

    return cluster_result

def preclustering():
    user_dict = {}
    
    if os.path.exists(os.path.join(ROOT_PATH, USER_DICT_NAME)):
        with open(os.path.join(ROOT_PATH, USER_DICT_NAME),'r',encoding='utf-8') as f:
            line = f.readline()
            while line:
                line = line.split('\t')
                user_dict[line[0]] = int(line[1])
                line = f.readline()
    else:
        user_dict = getuserdict()

    style_dict = {}

    if os.path.exists(os.path.join(ROOT_PATH, STYLE_DICT_NAME)):
        with open(os.path.join(ROOT_PATH, STYLE_DICT_NAME),'r',encoding='utf-8') as f:
            line = f.readline()
            while line:
                line = line.split('\t')
                style_dict[line[0]] = int(line[1])
                line = f.readline()
    else:
        style_dict = getstyledict()

    raw_record = []

    if os.path.exists(os.path.join(ROOT_PATH, RAW_RECORD_NAME)):
        with open(os.path.join(ROOT_PATH, RAW_RECORD_NAME),'r',encoding='utf-8') as f:
            line = f.readline()
            while line:
                line = line.split('\t')
                raw_record.append((line[0], line[1], int(line[2])))
                line = f.readline()
    else:
        raw_record = getrawrecord()
    
    matrix = getfeaturematrix(user_dict, style_dict, raw_record)

    cluster_result = {}

    if os.path.exists(os.path.join(ROOT_PATH, CLUSTER_RESULT_NAME)):
        with open(os.path.join(ROOT_PATH, CLUSTER_RESULT_NAME),'r',encoding='utf-8') as f:
            line = f.readline()
            while line:
                line = line.split('\t')
                cluster_result[line[0]] = int(line[1])
                line = f.readline()
    else:
        kmeans_model = KMeans(CLUSTER_NUM, random_state=1)
        cluster_result = getclusterresult(user_dict, matrix, kmeans_model)

    return cluster_result

def user_score_file(cluster_result,filename):
    user_list = [[] for _ in range(CLUSTER_NUM)] 
    with open(filename,'r',encoding = 'utf-8') as f:
        line = f.readline()
        while line:
            user_id = line.split(',')[0]
            cluster = cluster_result[user_id]
            user_list[cluster].append(line.strip())
            line = f.readline()
    for clusters in range(CLUSTER_NUM):
        with open(os.path.join('.','static','data','user_score'+str(clusters)+'.txt'),'w',encoding='utf-8') as f:
            for record in user_list[clusters]:
                f.write(record+'\n')
    return user_list
if __name__ == '__main__':
    cluster_result = preclustering()
    print(user_score_file(cluster_result,r'C:\\Users\\89556\\Desktop\\Music2\\Music2\\static\\data\\user_score.txt'))