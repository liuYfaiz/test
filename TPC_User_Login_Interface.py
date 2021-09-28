#!/usr/bin/python
# -*- coding:UTF-8 -*-

import asyncio
from mysqlWorker import *
from LKD_Tools import *
from kwl_py_log import *
from redis_operator import *
from Validate_Phone import *
from Util_Funcs import *
import hashlib
import time
from Util_Funcs import *
import requests
from WXBizDataCrypt import *

# 验证用户身份
async def Wechat_Validate(ref_request,sCode):
        # appid = 'wx09cfacb2d21da63f'
        # secret = '01db60225f8b4f16e2d1c12c21e2c844'
        # url = '''https://api.weixin.qq.com/sns/jscode2session?appid=wx5b298e3639e1d7cc&secret=076a8a156c4632d7dfd4b088313df5e4&js_code=%s&grant_type=authorization_code ''' % (sCode)
        url = '''https://api.weixin.qq.com/sns/jscode2session?appid=wx8b2b3fcff729a3b6&secret=076a8a156c4632d7dfd4b088313df5e4&js_code=%s&grant_type=authorization_code ''' % (sCode)
        r = requests.get(url)  # 最基本的GET请求
        userInfo = json.loads(r.text)

        kwl_py_write_log(str(userInfo), str(url), 2, msgid=ref_request)
        try:
            sOpenID = str(userInfo['openid'])
            strKey = str(userInfo['session_key'])
            return 0,'获取成功',sOpenID,strKey
        except Exception as e:
            return 3, '获取失败','',''


async def TPC_User_Login_Interface(ref_request, jsonlkdReq):
    try:
        reqDict = jsonlkdReq['REQUEST']['DATA']
        reqHeaderDict = jsonlkdReq['REQUEST']['HDR']
        if 'OTYPE' not in reqHeaderDict.keys():
            code = 2
            strErrMsg = '操作代码必须传入'
            return SetMsgAndBody(ref_request, code, strErrMsg, '', [])
        else:
            operateType = reqHeaderDict['OTYPE']

        kwl_py_write_log('2345r', 'xy: ', 2, msgid=ref_request)

        if 1 == operateType:  # 获取验证码
            if 'USER_MOBILE' not in reqDict.keys():
                code = 3
                strErrMsg = '缺少手机号'
                return SetMsgAndBody(ref_request, code, strErrMsg, '', [])

            strMobile = reqDict['USER_MOBILE']
            # 验证码
            code, strErrMsg = await TPC_Send_SMS_TO_Phone(ref_request,strMobile)
            if (code != '0'):
                code = 5
                strErrMsg = '系统数据出错，请联系维护人员'
                return code, strErrMsg

            return SetMsgAndBody(ref_request, code, '获取成功', '', [])

        elif 2 == operateType:  # 获取用户信息并生成对应的userid和session
            if 'TOKEN' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, 'token必须传入', '', [])

            strToken = str(reqDict['TOKEN'])
            iCurrenTime = int(time.time())
            ansData = []
            ansTmp = {}
            try:
                # 正式环境
                #url = '''https://zy.lshopes.com/api/decodeToken?userToken=''' + strToken
                # 测试环境
                url =  '''https://hz.lshopes.com/api/decodeToken?userToken=''' + strToken
                kwl_py_write_log(str(url), '', 2, msgid=ref_request)
                try:
                    r = requests.get(url, verify=False)  # 最基本的GET请求，绕过证书验证
                    userInfo = json.loads(r.text)
                    ansTmp['USER_NAME'] = userInfo['user']['nickname']
                    ansTmp['USER_PHONE'] = userInfo['user']['phone']
                    ansTmp['OPEN_ID'] = userInfo['user']['openid']
                    ansTmp['USER_PIC'] = userInfo['user']['img']
                except Exception as e:
                    # 测试用 写死
                    strTime = str(int(time.time()))
                    ansTmp['USER_NAME'] = '游客'+strTime
                    ansTmp['USER_PHONE'] = 'test'
                    ansTmp['OPEN_ID'] = 'test'
                    ansTmp['USER_PIC'] = 'https://service.linkda.com.cn/file/file/1574683520241.png'
                # 保存到数据库 存用户信息 并生成session
                sqlInsert = ''' INSERT INTO TPC_Users (CELLPHONE,NAME,OPEN_ID,LAST_LOGIN_TIME) VALUES ('%s','%s','%s',%d)  ON DUPLICATE KEY UPDATE LAST_LOGIN_TIME = %d
                            ''' % (str(ansTmp['USER_PHONE']), str(ansTmp['USER_NAME']), str(ansTmp['OPEN_ID']), iCurrenTime, iCurrenTime)
                code, msgText, ansList = await mysqlCommWorker(ref_request, sqlInsert, 3)

                rediskey = str(ansTmp['OPEN_ID'])
                if rediskey != 'test':
                    strTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                    src = rediskey + strTime + 'lkd2022'
                    sessionINDB = get_redis_key(rediskey)
                    kwl_py_write_log(str(sessionINDB), 'sessionINDB: ', 2, msgid='22')
                    redisvalue = ''
                    if str(sessionINDB) == 'None':
                        m2 = hashlib.md5()
                        m2.update(src.encode('utf-8'))
                        redisvalue = m2.hexdigest()
                        kwl_py_write_log(redisvalue, 'kkk: ', 2, msgid=ref_request)
                        set_redis_key_ex(rediskey, redisvalue, 60 * 60 * 5)
                    else:
                        redisvalue = sessionINDB.decode('UTF-8')
                    kwl_py_write_log(str(redisvalue), 'sessionINDB: ', 2, msgid='22')
                    ansTmp['SESSION'] = redisvalue
                else:
                    ansTmp['SESSION'] = ''
                kwl_py_write_log(str(ansTmp), 'sessionINDB: ', 2, msgid='22')

            except Exception as e:
                ansTmp['USER_NAME'] = ''
                ansTmp['USER_PHONE'] = ''
                ansTmp['OPEN_ID'] = ''
                ansTmp['USER_PIC'] = ''
                ansTmp['SESSION'] = ''
            ansData.append(ansTmp)
            return SetMsgAndBody(ref_request, 0, '获取成功', '', ansData)

        elif 3 == operateType:
            pass

        elif 4 == operateType:
            if 'OPEN_ID' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, 'openID必须传入', '', [])
            
            if 'USER_NAME' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, '用户姓名必须传入', '', [])
            
            if 'USER_PHONE' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, '用户手机号必须传入', '', [])
            
            if 'USER_PIC' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, '用户图片必须传入', '', [])

            strOpenID = str(reqDict['OPEN_ID'])
            strName = str(reqDict['USER_NAME'])
            strPhone = str(reqDict['USER_PHONE'])
            strPic = str(reqDict['USER_PIC'])
            iCurrenTime = int(time.time())

            ansData = []
            ansTmp = {}
    
            ansTmp['OPEN_ID'] = strOpenID
            
            sqlInsert = ''' INSERT INTO TPC_Users (CELLPHONE,NAME,OPEN_ID,LAST_LOGIN_TIME,USER_PIC) VALUES ('%s','%s','%s',%d,'%s')  ON DUPLICATE KEY UPDATE LAST_LOGIN_TIME = %d
                                ''' % (strPhone,strName,strOpenID,iCurrenTime,strPic,iCurrenTime)
            code, msgText, ansList = await mysqlCommWorker(ref_request, sqlInsert, 3)
            
            rediskey = str(ansTmp['OPEN_ID'])
            if rediskey != 'test':
                strTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                src = rediskey + strTime + 'lkd2022'
                sessionINDB = get_redis_key(rediskey)
                kwl_py_write_log(str(sessionINDB), 'sessionINDB: ', 2, msgid='22')
                redisvalue = ''
                if str(sessionINDB) == 'None':
                    m2 = hashlib.md5()
                    m2.update(src.encode('utf-8'))
                    redisvalue = m2.hexdigest()
                    kwl_py_write_log(redisvalue, 'kkk: ', 2, msgid=ref_request)
                    set_redis_key_ex(rediskey, redisvalue, 60 * 60 * 5)
                else:
                    redisvalue = sessionINDB.decode('UTF-8')
                kwl_py_write_log(str(redisvalue), 'sessionINDB: ', 2, msgid='22')
                ansTmp['SESSION'] = redisvalue
            else:
                ansTmp['SESSION'] = ''
                
            ansData.append(ansTmp)
            
            return SetMsgAndBody(ref_request, 0, '获取成功', '', ansData)
        
        elif 5 == operateType:
            if 'openID' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, 'openID必须传入', '', [])
    
            strOpenID = str(reqDict['openID'])
            ansData = []
            ansTmp = {}

            strTime = str(int(time.time()))
            ansTmp['USER_NAME'] = '游客' + strTime
            ansTmp['USER_PHONE'] = 'test'
            ansTmp['OPEN_ID'] = 'test'
            ansTmp['USER_PIC'] = 'https://service.linkda.com.cn/file/file/1574683520241.png'
            
            sqlSelect = ''' SELECT * FROM TPC_Users WHERE OPEN_ID = '%s' '''%(strOpenID)
            code, msgText, ansList = await mysqlCommWorker(ref_request, sqlSelect, 3)
            if len(ansList) != 0:
                ansTmp['USER_NAME'] = str(ansList[0]['NAME'])
                ansTmp['USER_PHONE'] = str(ansList[0]['CELLPHONE'])
                ansTmp['OPEN_ID'] = strOpenID
                ansTmp['USER_PIC'] = str(ansList[0]['USER_PIC'])
                rediskey = str(ansTmp['OPEN_ID'])
                if rediskey != 'test':
                    strTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                    src = rediskey + strTime + 'lkd2022'
                    sessionINDB = get_redis_key(rediskey)
                    kwl_py_write_log(str(sessionINDB), 'sessionINDB: ', 2, msgid='22')
                    redisvalue = ''
                    if str(sessionINDB) == 'None':
                        m2 = hashlib.md5()
                        m2.update(src.encode('utf-8'))
                        redisvalue = m2.hexdigest()
                        kwl_py_write_log(redisvalue, 'kkk: ', 2, msgid=ref_request)
                        set_redis_key_ex(rediskey, redisvalue, 60 * 60 * 5)
                    else:
                        redisvalue = sessionINDB.decode('UTF-8')
                    kwl_py_write_log(str(redisvalue), 'sessionINDB: ', 2, msgid='22')
                    ansTmp['SESSION'] = redisvalue
                else:
                    ansTmp['SESSION'] = ''
                    
            ansData.append(ansTmp)
            return SetMsgAndBody(ref_request, 0, '获取成功', '', ansData)
        
        elif 6 == operateType: # 获取session_key openid
            if 'JS_CODE' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, 'token必须传入', '', [])
            strCode = str(reqDict['JS_CODE'])
            
            ansData = []
            ansTmp = {}
            ansTmp_1 = {}
            
            code,msg,strOpenID,strKey = await Wechat_Validate(ref_request,strCode)
            ansTmp['openid'] = strOpenID
            ansTmp['session_key'] = strKey
            sqlSelect = '''SELECT ID,CELLPHONE FROM TPC_Users WHERE OPEN_ID = '%s' AND CELLPHONE IS NOT NULL AND CELLPHONE <> 'tset'  '''%(strOpenID)
            code, msgText, ansList = await mysqlCommWorker(ref_request, sqlSelect, 1)
            if len(ansList) == 0:
                ansTmp_1['flag'] = 0
                ansTmp_1['cellphone'] = '0'
            else:
                ansTmp_1['flag'] = 1
                ansTmp_1['cellphone'] = str(ansList[0]['CELLPHONE'])
            
            ansData.append(ansTmp)
            ansData.append(ansTmp_1)
            return SetMsgAndBody(ref_request, 0, '获取成功', '', ansData)
        
        elif 7 == operateType: # 解析encryptedData
            if 'APP_ID' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, 'APP_ID必须传入', '', [])
            
            if 'session_key' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, 'session_key必须传入', '', [])
            
            if 'encryptedData' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, 'encryptedData必须传入', '', [])
            
            if 'iv' not in reqDict.keys():
                return SetMsgAndBody(ref_request, 3, 'iv必须传入', '', [])

            appId = str(reqDict['APP_ID'])
            sessionKey = str(reqDict['session_key'])
            encryptedData = reqDict['encryptedData']
            iv = str(reqDict['iv'])

            pc = WXBizDataCrypt(appId, sessionKey)
            ansList = pc.decrypt(encryptedData, iv)

            return SetMsgAndBody(ref_request, 0, '获取成功', '', ansList)
            
        else:
            code = 2
            strErrMsg = '错误的操作代码'
            return SetMsgAndBody(ref_request, code, strErrMsg, '', [])

    except Exception as e:
        kwl_py_write_log('系统内部出错，请联系系统维护人员: ' + repr(e), '用户登录出错: ', 2, msgid=ref_request)
        code = -1003
        strErrMsg = '系统内部出错，请联系系统维护人员'
        return SetMsgAndBody(ref_request, code, strErrMsg, '', [])

