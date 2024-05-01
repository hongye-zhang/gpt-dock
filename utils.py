# some utils functions
import hashlib

GPTPROMPTWORD = '(#@咒@#)'
GPTTRANSLATEWORD = '(#@翻@#)'
GPTSPECIFICWORDS = [GPTPROMPTWORD, GPTTRANSLATEWORD]

ERRORWORD = '#Error#: '

# used to split each key point, should be removed when we make pdfs
PROMPTSPLITWORD = '\n------prompt------\n'
KEYPOINTSPLITWORD = '\n------keypoint------\n'
LISTSPLITWORD = '\n------klist------\n'

LANGUAGETABLE = {}
# 是否包含任意一个关键字
def containAnyKeyword(paragraph, keywordlist, mustequal=False):
    # 如果没指定关键字，则认为是包含的
    if keywordlist is None or len(keywordlist) == 0:
        return True
    for keyword in keywordlist:
        if mustequal:
            if keyword == paragraph:
                return True
        else:
            if keyword in paragraph:
                return True
    return False

# split list to n parts
def splitList(a, n):
    k, m = divmod(len(a), n)
    return list(a[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(n))

# clean the specific char for GPT
def cleanStringForGPT(oristr):
    newstr = oristr
    for gptword in GPTSPECIFICWORDS:
        newstr = newstr.replace(gptword, '')

    return newstr

# get unique id for a string
def getStringUniqueID(oristr, digitals=6):
    realstr = oristr
    if isinstance(oristr, list):
        realstr = ''
        for eachitem in oristr:
            if isinstance(eachitem, str):
                realstr = realstr + str(eachitem)
            elif isinstance(eachitem, tuple):
                for eachitemitem in eachitem:
                    realstr = realstr + str(eachitemitem)

    hashstr = hashlib.md5(realstr.encode('utf-8')).hexdigest()
    return hashstr[:digitals]

# detect language of a string
def detectLanguage(oristr):
    from langdetect import detect_langs
    from languagecode import LANGUAGE_ISO_639
    detectstr = oristr[:256]
    langs = detect_langs(detectstr)
    if langs is None or len(langs) == 0:
        return None

    firstlang = langs[0]
    firstcode = firstlang.lang

    for languagedata in LANGUAGE_ISO_639:
        if firstcode == languagedata[0]:
            return languagedata[1]

    return None

# whether the text need to be translated
def needTranslate(oristr, languagename):
    strlang = detectLanguage(oristr)
    if strlang == languagename:
        return False

    return True

# only return letter and number, so easy to compare
def onlyLetterAndNumber(oristr):
    import re
    result = re.sub(u'[\W_]+', u'', oristr, flags=re.UNICODE)  # support unicode
    return result

# contains at least a number
def has_numbers(inputString):
    return any(char.isdigit() for char in inputString)

# contains at least a letter
def has_letters(inputString):
    return any(char.isalpha() for char in inputString)

# find small title, which begins with 1, 1.1 such kind of things
def isSmallTitle(titletext, sectiononly=False, rettaglevel=False, retnumber=False):
    import re
    taglevel = -1
    restr = r"^\d+(?:\.\d+)* *"
    if sectiononly:
        restr = r"^\d{1,3}\.(?:\d{1,3}\.?)* *"
    numberings = re.findall(restr, titletext)
    if len(numberings) > 0:
        taglevel = numberings[0].count(".") + 1
        if retnumber:
            return numberings[0].strip()

    if rettaglevel:
        return taglevel

    if taglevel == -1:  # 找不到编号，则直接忽略
        return False

    return True

# compress string, no digital and punc
def compressDigital(oristr):
    if oristr is None or len(oristr) == 0:
        return oristr

    compressstr = ''.join(x for x in oristr if x.isalpha() or x == ' ')
    return compressstr

