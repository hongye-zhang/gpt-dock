# split pdf file to chunks according outline of pdf
import json
import os.path
import re

from operator import itemgetter
import fitz
from thefuzz import fuzz  # string similarity package

from utils import containAnyKeyword, onlyLetterAndNumber, isSmallTitle, has_letters, has_numbers, compressDigital

CONTENTSSTRING = ["Contents", "Table of Contents", "Inhaltsverzeichnis", "目录"]
ENDSTRING = [
    "Literaturverzeichnis",
    "Index",
    "Acknowledgments",
    "Copyright",
    "Literaturverzeichnis",
    "References",
]
ENDCONTAINSTRING = ["Appendix A", "Appendix B", "Appendix C", "Appendix D"]
PUNCLIST = '''\,;:!\(\)\+-=\[\]\{\}'"<>.\/\?@#\$%\^&\*·_~、，（）；。：”“’‘'''

# max chars that need to split because of openai token limit
MAXSPLITCHARS = 100000

# 用户通常不会给出maintitle，因此，主要依赖于系统自动解析。
class BearParsePDF:
    def __init__(self, pdf_filename, maintitle=None):
        self.pdf_filename = pdf_filename
        self.maintitle = maintitle
        if not os.path.exists(pdf_filename):
            print('Cannot find the pdf file! ')
            exit()

        # members needed
        self.pdf_textsize = 0

        self.document = fitz.open(self.pdf_filename)

        self.corebbox = [0, 0, 10000, 10000]
        self.corebboxodd = [0, 0, 10000, 10000]  # 有可能需要区分单双页
        self.stdtextsize = 10

        self.alltitles = None
        self.outline = None  # final outline

        self.bookmarks = []  # bookmark outline
        self.contents = []  # content outline
        self.fontoutline = []  # outline from fontsize

        self.allsizetitles = {}  # save title data according fontsize
        self.maintitle = None
        self.aftercontents = None  # 跳过pdf中的目录结构
        self.contentbegin = 0  # 正式内容开始的编号
        self.contentend = None  # 真是内容结束的编号
        self.chunks = None  # pdf chunks
        self.fakelasttitle = False  # whether there is a fake last title

    # private functions
    def _detectBBox(self):
        self.corebbox, stdfontsizeleft = self._findPDFCoreBBox()
        self.corebboxodd, stdfontsizeright = self._findPDFCoreBBox(odd=True)
        self.stdtextsize = max(stdfontsizeleft, stdfontsizeright)

    # find the full width line, so we can calc the core of pdf.
    # the method is simple, full width line of all pages should makeup the core
    # for large size pdfs, this method should be accurate, for small pdfs, this method won't be accurate
    # so the method is only used to filter header and footer
    # many pdf has different left page and right page, so the bbox is different for left/right pages
    def _findPDFCoreBBox(self, odd=False):
        # array for lines
        lines_width_list = []
        lines_charcount_list = []
        for pageindex, page in enumerate(self.document):
            if odd:
                if pageindex % 2 == 1:
                    continue
            else:
                if pageindex % 2 == 0:
                    continue

            pagetext = ''
            blocks = page.get_text("dict")["blocks"]
            for bindex, b in enumerate(blocks):  # iterate through the text blocks
                blocktext = ''
                if b["type"] == 0:  # block contains text
                    for l in b["lines"]:  # iterate through the text lines
                        # Ignore the vertical textbox
                        wdir = l["dir"]  # writing direction = (cosine, sine)
                        if wdir[0] == 0:  # either 90° or 270°
                            continue
                        linewidth = l["bbox"][2] - l["bbox"][0]
                        lines_width_list.append(round(linewidth))
                        linecount = 0
                        for s in l["spans"]:  # iterate through the text spans
                            blocktext = blocktext + s["text"]
                            linecount += len(s["text"])

                        lines_charcount_list.append(linecount)

                    b["text"] = blocktext

                pagetext = pagetext + '\n' + blocktext
            pass

        # unify line width according to max char count
        # get the avergage char count of lines_charcount_list
        avgcharcount = round(sum(lines_charcount_list)/len(lines_charcount_list))
        maxlinewidth = max(lines_width_list)
        charunit = int(maxlinewidth / avgcharcount)
        for index, linewidth in enumerate(lines_width_list):
            lines_width_list[index] = round(linewidth / charunit)

        mostwidth = max(set(lines_width_list), key=lines_width_list.count)

        # find core bbox
        bbleft = 10000
        bbright = 0
        bbtop = 10000
        bbbottom = 0
        font_size_list = []
        for pageindex, page in enumerate(self.document):
            if odd:
                if pageindex % 2 == 1:
                    continue
            else:
                if pageindex % 2 == 0:
                    continue

            blocks = page.get_text("dict")["blocks"]
            for bindex, b in enumerate(blocks):  # iterate through the text blocks
                if b["type"] == 0:  # block contains text
                    for l in b["lines"]:  # iterate through the text lines
                        # Ignore the vertical textbox
                        wdir = l["dir"]  # writing direction = (cosine, sine)
                        if wdir[0] == 0:  # either 90° or 270°
                            continue
                        linewidth = l["bbox"][2] - l["bbox"][0]
                        unifywidth = round(linewidth / charunit)
                        if unifywidth == mostwidth:
                            if l["bbox"][0] < bbleft:
                                bbleft = l["bbox"][0]
                            if l["bbox"][2] > bbright:
                                bbright = l["bbox"][2]
                            if l["bbox"][1] < bbtop:
                                bbtop = l["bbox"][1]
                            if l["bbox"][3] > bbbottom:
                                bbbottom = l["bbox"][3]

                            for s in l["spans"]:  # iterate through the text spans
                                fontsize = s["size"]
                                if fontsize not in font_size_list:
                                    font_size_list.append(fontsize)

        corebbox = [bbleft, bbtop, bbright, bbbottom]
        stdtextsize = round(max(font_size_list) * 2) / 2
        return (corebbox, stdtextsize)

    # filter inproper lines, including vertical line, header and footer
    def _filterLines(self, line, odd=False):
        # filter vertical lines
        wdir = line["dir"]  # writing direction = (cosine, sine)
        if wdir[0] == 0:  # either 90° or 270°
            return True

        corebbox = self.corebbox
        if odd:
            corebbox = self.corebboxodd

        # python two bbox not intersect horizontally
        if line["bbox"][2] < corebbox[0] or line["bbox"][0] > corebbox[2]:
            return True
        # python two bbox not intersect vertically
        if line["bbox"][3] < corebbox[1] or line["bbox"][1] > corebbox[3]:
            return True

        return False

    # end private functions

    # API functions
    # get the text size of pdf, which will be used to roughly calc price to parse pdf
    # by now we have only text size, but maybe we can return more info in the future
    def parsePDFMetaInfo(self):
        # get the total pdf text amount
        for page in self.document:
            text = page.get_text()
            self.pdf_textsize += len(text)

        return self.pdf_textsize

    # parse pdf file to chunks according to outline
    def parsePDFOutlineAndSplit(self):
        self.parseContents()  # parse the basic structure of the pdf
        self.parsePDFOutline()  # parse the pdf file to get outline
        self.chunks = self.makeChunkByOutline(self.outline, self.contentbegin)
        result = json.dumps(self.chunks, ensure_ascii=False)
        return result
        pass

    # end API functions

    def parseContents(self):
        self._detectBBox()
        doc = self.document

        font_counts, styles = self.fonts(self.document, granularity=False)
        size_tag = self.font_tags(font_counts, styles)

        self.elements = self.headers_para(doc, size_tag)
        # 清理self.elements，每个elements必须是一个单独的行，忽略行中间的细节信息，这些细节对于寻找
        # 标题，是没有帮助的
        newelements = []
        elecache = []
        for theelement in self.elements:
            if '\r' in theelement:
                if len(elecache) > 0:
                    theelement = ' '.join(elecache) + theelement
                newelements.append(theelement)
                elecache = []
            else:
                elecache.append(theelement)

        self.elements = newelements

        if self.maintitle is None:
            self.findMaintitle()  # get the maintitle

        self.findAllTitles()  # get all the element with title tag, just for mankind easy to check results

    def parsePDFOutline(self):
        # if pdf file has bookmarks, try to find it and get outline
        if self.document.outline is not None:
            self.parseOutlineFromBookmarks(self.document.outline, self.bookmarks)
            # 清理掉一些不需要的目录
            newbookmarks = []
            for bookmark in self.bookmarks:
                if bookmark[1] in CONTENTSSTRING:
                    continue
                elif bookmark[1] in ENDSTRING:
                    break
                newbookmarks.append(bookmark)
            self.bookmarks = newbookmarks

        self.outlinetitlelist = []
        # then we try to get the content/Inhaltsverzeichnis
        # Notice: We DONNOT read outline from Contents section of the pdf, instead we read each title
        # two reasons: 1. the contents section is not always correct, 2. the contents section is not always equal to
        # real titles. So we read outline directly from titles
        self.parseOutlineFromContents()
        self.parseOutlineFromFontSize()

        contents = self.fontoutline

        # 有的图书，默认书签的长度不正确，需要过滤掉
        if len(self.bookmarks) > 0 and len(self.contents) >= 0 and len(self.bookmarks) > len(contents) * 0.8:  # 如果有合适的书签，就用书签
            self.outline = self.bookmarks
        else:
            self.outline = contents

        if self.outline is None:
            # then, we try to get outline just according to fontsize
            self.outline = self.fontoutline

        if self.outline is not None:
            self.cleanOutline()
            self.maxtitlelevel = max([x[0] for x in self.outline])
        pass

    # clean the outline whether its source
    def cleanOutline(self):
        outlinelist = []
        lasttitle = None
        for index, outlineitem in enumerate(self.outline):
            lasttitle = outlineitem[1]
            if containAnyKeyword(lasttitle, ENDSTRING, mustequal=True) and not self.fakelasttitle:
                break
            outlinelist.append(outlineitem)

        self.outline = outlinelist

        # 清理self.elements
        elecount = len(self.elements)
        newelements = []
        for index, element in enumerate(self.elements):
            if len(element) == 0:
                newelements.append(element)
                continue
            tags = re.findall(r"<[^>]+>", element)
            if len(tags) > 0:
                tag = tags[0]
                if "h" in tag:
                    taglevel = int(tag[2:3])
                    titletext = element.replace(tag, "").replace("\r", "").strip()
                    if (
                        titletext == lasttitle and index > elecount * 0.7
                    ):  # 找到目录的起点, # 位置太靠前的，不太可能是结束位置
                        break

            newelements.append(element)

        self.elements = newelements

    # parse the pdf outline
    def parseOutlineFromBookmarks(self, docoutline, outlinelist, level=1):
        outlinelist.append([level, docoutline.title])
        if docoutline.down is not None:
            self.parseOutlineFromBookmarks(docoutline.down, outlinelist, level + 1)
        if docoutline.next is not None:
            self.parseOutlineFromBookmarks(docoutline.next, outlinelist, level)
        pass

    # parse the pdf outline from contents
    def parseOutlineFromContents(self):
        import string

        startindex = None
        startlevel = None
        endindex = None
        endlevel = None
        elecount = len(self.elements)
        for index, element in enumerate(self.elements):
            if len(element) == 0:
                continue
            tags = re.findall(r"<[^>]+>", element)
            if len(tags) > 0:
                tag = tags[0]
                if "h" in tag:
                    taglevel = int(tag[2:3])
                    titletext = element.replace(tag, "").replace("\r", "").strip()
                    if titletext in CONTENTSSTRING:  # 找到目录的起点
                        if startindex is None:
                            startindex = index
                            startlevel = taglevel
                    elif titletext in ENDSTRING or containAnyKeyword(
                        titletext, ENDCONTAINSTRING
                    ):  # 找到目录的终点
                        endindex = index
                        endlevel = taglevel
                        if endindex > elecount * 0.7:  # 位置太靠前的，不太可能是结束位置
                            self.contentend = endindex

        if startindex is None:
            return None

        outline = []
        index = 0
        firstlevel = 0  # level of the first content title
        for index, element in enumerate(self.elements):
            if index <= startindex:
                continue

            tags = re.findall(r"<[^>]+>", element)
            if len(tags) > 0:
                tag = tags[0]
                tagnumber = re.findall(r"\d+", tag)
                taglevel = -1
                if len(tagnumber) > 0:
                    taglevel = int(tagnumber[0])

                orititletext = element.replace(tag, "").replace("\r", " ").strip()
                titlelevel = -1
                if "h" in tag:
                    if int(taglevel) <= startlevel or int(taglevel) < firstlevel or index > 800:  # 设置最大段落，一般目录不太可能很靠后
                        break
                    else:  # 容错代码，如果没有数字，但是在目录结构中，标签是标题，也认为是标题格式
                        titlelevel = 1

                if len(orititletext) > 0:
                    # 分析目录的真正层级
                    orititletext = orititletext.replace('\r', ' ')  # 目录区域，标题行中不应该包含回车
                    # 有的pdf，多行目录可能被合并到一行了，需要进行分行。需要分行的，一定是section方式，1.1之类
                    splits = re.findall(r'\d{1,3}\.?(?:\d{1,3}\.?)*\D*', orititletext)
                    if splits is None or len(splits) == 0:  # 不是小节标题
                        titletext = orititletext
                        numberings = re.findall(r"^\d+(?:\.\d+)* *", titletext)
                        if len(numberings) > 0:
                            titlelevel = numberings[0].count(".") + 1

                        if titlelevel == -1:  # 找不到编号，则直接忽略
                            continue

                        # if title don't include page numbering, just ignore it
                        if not has_numbers(titletext):
                            continue

                        titletext = re.sub(r"[\d\-]+$", "", titletext)
                        titletext = titletext.replace(" .", "")
                        titletext = titletext.strip()

                        outline.append([titlelevel, titletext])

                        if firstlevel == 0:
                            firstlevel = taglevel
                        else:
                            if taglevel < firstlevel and taglevel != -1:
                                firstlevel = taglevel
                    else:
                        for titletext in splits:
                            titlelevel = -1
                            numberings = re.findall(r"^\d+(?:\.\d+)* *", titletext)
                            if len(numberings) > 0:
                                titlelevel = numberings[0].count(".") + 1

                            if titlelevel == -1:  # 找不到编号，则直接忽略
                                continue

                            titletext = re.sub(r"[\d\-]+$", "", titletext)
                            titletext = titletext.replace(" .", "")
                            titletext = titletext.strip()

                            if len(titletext) > 0 and ' ' in titletext:
                                outline.append([titlelevel, titletext])

                            if firstlevel == 0:
                                firstlevel = taglevel
                            else:
                                if taglevel < firstlevel and taglevel != -1:
                                    firstlevel = taglevel

        # 获取目录之后的行的内容
        self.contentbegin = index

        lastcontent = self.elements[index]
        tags = re.findall(r"<[^>]+>", lastcontent)
        if len(tags) > 0:
            tag = tags[0]
            lastcontent = lastcontent.replace(tag, "")

        lastcontent = lastcontent.replace("\r", " ").strip()
        self.aftercontents = lastcontent

        self.contents = outline
        pass

    # analysis document. find the outline and save in a json structure
    # First we need to decide whether the titles has number in the front, method is to statistic all the titles
    # if has number titles exceed 60%, we think it need number. and, sometimes there will be chapter 1, 2, such kind of formats
    # so titles contain number is also acceptable
    def parseOutlineFromFontSize(self):
        title_has_number = 0
        start_number = len(self.alltitles)
        end_number = 0
        for index, element in enumerate(self.alltitles):
            titletext = element[2]
            if titletext[0].isnumeric() or 'Chapter' in titletext or 'chapter' in titletext or 'Kapitel' in titletext:
                title_has_number += 1

                if index < start_number:
                    start_number = index

                if index > end_number:
                    end_number = index

        first_title_number_at_begin = True
        if title_has_number / len(self.alltitles) > 0.5:
            first_title_number_at_begin = True
        else:
            first_title_number_at_begin = False

        if end_number < len(self.alltitles) - 1:
            self.fakelasttitle = True

        for index, element in enumerate(self.alltitles):
            taglevel = element[0]
            titletext = element[2]
            # filter main title
            if titletext == self.maintitle and taglevel == 1:
                continue

            if first_title_number_at_begin:
                # should be + 1, but we add one extra title for last title's content
                real_end_number = end_number + 1
                if self.fakelasttitle:
                    real_end_number = end_number + 2
                if index not in range(start_number, real_end_number):
                    continue

            self.fontoutline.append([taglevel, titletext])
        pass

    def parseOutlineFromFontSizeOld(self):
        fontsizeelements = self.elements
        allsizetitles = {}
        allsizeindex = {}
        for index, element in enumerate(fontsizeelements):
            if len(element) == 0:
                continue
            tags = re.findall(r"<[^>]+>", element)
            if len(tags) > 0:
                tag = tags[0]
                if "h" in tag:
                    taglevel = int(tag[2:3])
                    if len(allsizeindex) == 0 and taglevel == 1:
                        self.maintitle = element.replace(tag, "").replace("\r", "")
                        continue

                    if taglevel not in allsizeindex:
                        # if title level small than previous title, it must be fault
                        if (taglevel + 1) in allsizeindex or (
                            taglevel + 2
                        ) in allsizeindex:
                            continue
                        allsizeindex[taglevel] = index

                    if taglevel not in allsizetitles:
                        allsizetitles[taglevel] = []

                    titlelist = allsizetitles[taglevel]
                    titletext = element.replace(tag, "").replace("\r", "")
                    titlelist.append(titletext)
                    allsizetitles[taglevel] = titlelist
                    self.fontoutline.append([taglevel, titletext])

        self.allsizetitles = allsizetitles
        pass

    # find the first html tag, sample: <h68>Chapter 1
    def findTagsInElement(self, element, numberonly=False, titleonly=False):
        tags = re.findall(r"<[^>]+>", element)
        if len(tags) > 0:
            tag = tags[0]
            if titleonly:
                if 'h' not in tag:
                    return None

            if numberonly:
                tagnumber = re.findall(r"\d+", tag)
                taglevel = None
                if len(tagnumber) > 0:
                    taglevel = int(tagnumber[0])
                return taglevel

            return tag

        return None

    # Many books doesn't bookmark maintitle, so we can only get mantitle just by font size
    # find the most front 5 title and select the largest
    def findMaintitle(self):
        fontsizeelements = self.elements
        allsizeindex = {}

        maintitletag = 100
        maintitleindex = 0
        loopcount = 0
        for index, element in enumerate(fontsizeelements):
            if len(element) == 0:
                continue
            tags = re.findall(r"<[^>]+>", element)
            if len(tags) > 0:
                tag = tags[0]
                if "h" in tag:
                    tagcontent = int(tag[2:3])
                    if len(allsizeindex) == 0 and tagcontent < 3:
                        maintitle = element.replace(tag, "").replace("\r", "")
                        if loopcount >= 5:
                            break
                        loopcount += 1
                        if tagcontent < maintitletag:
                            maintitletag = tagcontent
                            maintitleindex = index
                            self.maintitle = maintitle

        return self.maintitle
        pass

    # find all title line in elements, just for mankind easy to check result
    def findAllTitles(self):
        fontsizeelements = self.elements
        alltitles = []
        for index, element in enumerate(fontsizeelements):
            if len(element) == 0:
                continue

            # only keep titles after table of contents
            if index < self.contentbegin:
                continue

            tags = re.findall(r"<([^>]+)>", element)
            if len(tags) > 0:
                tag = tags[0]
                if "h" in tag:
                    tagcontent = int(tag.replace('h', ''))
                    titlestr = (
                        element.replace(tag, "").replace("ﬁ", "fi").replace("\r", "").strip()
                    )
                    titlestr = self.cleanElementText(titlestr, loosemode=0)
                    if len(titlestr) > 0:
                        compresstitle = compressDigital(titlestr).strip()
                        alltitles.append([tagcontent, index, titlestr, compresstitle])

        # 过滤，删掉比最小的小标题级别更低的标题
        maxtitlelevellist = {}
        for thetitle in alltitles:
            titletext = thetitle[2].strip()
            taglevel = isSmallTitle(titletext, sectiononly=True, rettaglevel=True)
            if taglevel == -1:
                continue
            if taglevel not in maxtitlelevellist:
                maxtitlelevellist[taglevel] = thetitle[0]
            else:
                if thetitle[0] < maxtitlelevellist[taglevel]:
                    maxtitlelevellist[taglevel] = thetitle[0]

        levellist = list(maxtitlelevellist.values())
        if len(levellist) > 0:
            maxtitlelevel = max(levellist)
            if maxtitlelevel > 0:
                alltitles = [x for x in alltitles if x[0] <= maxtitlelevel]

        self.alltitles = alltitles

    def newsize(self, s):
        intfontsize = round(s["size"] * 2) / 2  # 字号按照1/2为单位设置，避免太多字号细节干扰
        # 黑体不能简单放大字号，很多段落黑体和正文混合，这样会导致字号不一致
        # 我们采取了一种trick，黑体稍微放大0.099，作为特殊的字号来处理.
        # s["flags"] = 2: italic, 16: bold
        if "Bold" in s["font"] or "bold" in s["font"] or s["flags"] >= 16:
            intfontsize += 0.099  # 黑体把字号稍稍放大点

        return intfontsize

    def fonts(self, doc, granularity=False):
        """Extracts fonts and their usage in PDF documents.

        :param doc: PDF document to iterate through
        :type doc: <class 'fitz.fitz.Document'>
        :param granularity: also use 'font', 'flags' and 'color' to discriminate text
        :type granularity: bool

        :rtype: [(font_size, count), (font_size, count}], dict
        :return: most used fonts sorted by count, font style information
        """
        styles = {}
        font_counts = {}

        for pageindex, page in enumerate(doc):
            odd = False
            if pageindex % 2 == 0:
                odd = True

            pagetext = ''
            blocks = page.get_text("dict")["blocks"]
            for bindex, b in enumerate(blocks):  # iterate through the text blocks
                blocktext = ''
                if b["type"] == 0:  # block contains text
                    for l in b["lines"]:  # iterate through the text lines
                        if self._filterLines(l, odd=odd):
                            continue

                        for s in l["spans"]:  # iterate through the text spans
                            if granularity:
                                identifier = "{0}_{1}_{2}_{3}".format(
                                    self.newsize(s), s["flags"], s["font"], s["color"]
                                )
                                styles[identifier] = {
                                    "size": self.newsize(s),
                                    "flags": s["flags"],
                                    "font": s["font"],
                                    "color": s["color"],
                                }
                            else:
                                identifier = f"{self.newsize(s)}"
                                styles[identifier] = {
                                    "size": self.newsize(s),
                                    "font": s["font"],
                                }

                            font_counts[identifier] = (
                                font_counts.get(identifier, 0) + 1
                            )  # count the fonts usage

                            blocktext = blocktext + s["text"]

                    b["text"] = blocktext
                pagetext = pagetext + '\n' + blocktext
            pass

        font_counts = sorted(font_counts.items(), key=itemgetter(1), reverse=True)

        if len(font_counts) < 1:
            raise ValueError("Zero discriminating fonts found!")

        return font_counts, styles

    def font_tags(self, font_counts, styles):
        """Returns dictionary with font sizes as keys and tags as value.

        :param font_counts: (font_size, count) for all fonts occuring in document
        :type font_counts: list
        :param styles: all styles found in the document
        :type styles: dict

        :rtype: dict
        :return: all element tags based on font-sizes
        """
        p_style = styles[
            font_counts[0][0]
        ]  # get style for most used font by count (paragraph)
        p_size = p_style["size"]  # get the paragraph's size

        # sorting the font sizes high to low, so that we can append the right integer to each tag
        ori_font_sizes = []
        for font_size, count in font_counts:
            real_font_size = float(font_size)
            if real_font_size not in ori_font_sizes:
                ori_font_sizes.append(real_font_size)

        map_ori_font_sizes = {}

        font_sizes = []
        for font_size, count in font_counts:
            real_font_size = float(font_size)
            ori_font_size = str(font_size)
            if '99' in font_size:
                try_font_size = real_font_size - 0.099
                if try_font_size != p_size:
                    map_ori_font_sizes[real_font_size] = try_font_size
                    real_font_size = try_font_size

            if real_font_size not in font_sizes:
                font_sizes.append(real_font_size)

        font_sizes.sort(reverse=True)

        # aggregating the tags for each font size
        idx = 0
        size_tag = {}
        for size in font_sizes:
            idx += 1
            if size == p_size:
                idx = 0
                size_tag[size] = "<p>"
            if size > p_size:
                size_tag[size] = "<h{0}>".format(idx)
            elif size < p_size:
                # size_tag[size] = '<s{0}>'.format(idx)
                size_tag[size] = "<p>"  # 小于P的，一律按照<s>统一处理，不再区分细节

        for size in ori_font_sizes:
            if size in map_ori_font_sizes:
                size_tag[size] = size_tag[map_ori_font_sizes[size]]

        return size_tag

    # 同样tag的合并，而不是同样字号的合并
    def getTag(self, newsize, size_tag):
        if newsize in size_tag:
            return size_tag[newsize]
        else:
            return "<p>"

    def headers_para(self, doc, size_tag):
        """Scrapes headers & paragraphs from PDF and return texts with element tags.

        :param doc: PDF document to iterate through
        :type doc: <class 'fitz.fitz.Document'>
        :param size_tag: textual element tags for each size
        :type size_tag: dict

        :rtype: list
        :return: texts with pre-prended element tags
        """
        header_para = []  # list with headers and paragraphs
        first = True  # boolean operator for first header
        previous_s = {}  # previous span

        for pageindex, page in enumerate(doc):
            odd = False
            if pageindex % 2 == 0:
                odd = True

            blocks = page.get_text("dict")["blocks"]
            for b in blocks:  # iterate through the text blocks
                if b["type"] == 0:  # this block contains text
                    # REMEMBER: multiple fonts and sizes are possible IN one block

                    block_string = ""  # text found in block
                    for l in b["lines"]:  # iterate through the text lines
                        if self._filterLines(l, odd=odd):
                            continue

                        for s in l["spans"]:  # iterate through the text spans
                            if s["text"].strip():  # removing whitespaces:
                                if first:
                                    previous_s = s
                                    first = False
                                    block_string = size_tag[self.newsize(s)] + s["text"]
                                else:
                                    if self.getTag(
                                        self.newsize(s), size_tag
                                    ) == self.getTag(
                                        self.newsize(previous_s), size_tag
                                    ):
                                        if block_string and all(
                                            (c == "|") for c in block_string
                                        ):
                                            # block_string only contains pipes
                                            block_string = (
                                                size_tag[self.newsize(s)] + s["text"]
                                            )
                                        if block_string == "":
                                            # new block has started, so append size tag
                                            block_string = (
                                                size_tag[self.newsize(s)] + s["text"]
                                            )
                                        else:  # in the same block, so concatenate strings
                                            block_string += " " + s["text"]

                                    else:
                                        header_para.append(block_string)
                                        block_string = (
                                            size_tag[self.newsize(s)] + s["text"]
                                        )

                                    previous_s = s

                        # new block started, indicating with a pipe
                        block_string += "\r"

                    header_para.append(block_string)

        return header_para

    # as per recommendation from @freylis, compile once only
    def cleanhtml(self, raw_html):
        cleantext = re.sub(r"<.*?>", "", raw_html)
        return cleantext

    # pdf的行，是否是合适的行，滤掉那些奇奇怪怪的文字
    # loosemode: 0:则不做过多的过滤，1:滤掉不像标题的  2，则执行更加严格的过滤，以减少送进gpt的无效文字
    def cleanElementText(self, oritext, loosemode=0):
        if oritext is None or len(oritext) == 0:
            return ""

        compressstr = self.cleanhtml(oritext)

        if loosemode == 0:
            return compressstr

        # 严格模式过滤，因此呢，不再过滤那些奇奇怪怪的文字了
        compressstr = "".join(
            x
            for x in compressstr
            if x.isalpha() or x.isdecimal() or x in PUNCLIST or x == ' '
        )

        if len(compressstr) <= 3:
            return ""

        # 是不是标题候选对象：1、包含1.1这样的东东，2、包含纯数字，例如Chapter 1这种。
        if loosemode == 1:
            if " " in compressstr:
                atleast = False
                splits = compressstr.split(" ")
                for split in splits:
                    if isSmallTitle(split):
                        atleast = True
                    elif split.isdecimal() and has_letters(split):  # 至少有一个数字和一个字符
                        atleast = True

                if not atleast:
                    return ""

            return compressstr

        # 滤掉纯数字和一个字母，减少gpt的输入
        if " " in compressstr:
            splits = compressstr.split(" ")
            newlist = []
            maxwordlen = 0
            for split in splits:
                if len(split) == 0:
                    continue
                if len(split) == 1 and split not in ["i", "a", "o", "I", "A", "O"]:
                    continue
                if split.isdecimal():
                    continue
                wordlen = len(split)
                if wordlen > maxwordlen:
                    maxwordlen = wordlen

                newlist.append(split)

            if len(newlist) > 0 and maxwordlen > 4:
                compressstr = " ".join(newlist)
            else:
                compressstr = ""

        return compressstr

    # 过滤生成好的content
    def filterContent(self, contentstr):
        if contentstr is None or len(contentstr) == 0 or '\r' not in contentstr:
            return contentstr

        splits = contentstr.split('\r')
        newlist = []
        for oritext in splits:
            newstr = self.cleanElementText(oritext, loosemode=2)
            if len(newstr) > 0:
                newlist.append(newstr)

        if len(newlist) == 0:
            return contentstr

        newcontent = '\r'.join(newlist)
        return newcontent

    # 判断目录行和element的行是否完全相等
    # 很多pdf文件，目录行和正文，有轻微差别，所以不能直接用 == 判断
    # 注：使用fuzz之后，速度非常慢。所以，我们直接从正文中读取title，并且直接简单地字符串对比
    def isidential(self, outlinestr, elementstr, nextstr="", threshold=95):
        if outlinestr == elementstr:
            return True

        return False
        pass

    def isidentialfuzz(self, outlinestr, elementstr, nextstr="", threshold=95):
        outlinecompress = "".join(
            x for x in outlinestr if x.isalpha() or x.isdecimal() or x == "."
        )
        elementcompress = "".join(
            x for x in elementstr if x.isalpha() or x.isdecimal() or x == "."
        )
        nextcompress = "".join(
            x for x in nextstr if x.isalpha() or x.isdecimal() or x == "."
        )
        if fuzz.ratio(elementcompress, outlinecompress) >= threshold:
            return True
        elif fuzz.ratio(elementcompress + nextcompress, outlinecompress) >= threshold:
            return True
        else:  # only difference is numbering
            leftstr = outlinecompress.replace(elementcompress, "").strip()
            if leftstr.isdecimal():
                return True

        return False

    # 将所有的标题组成一个列表，页眉和页脚中经常会出现标题，产生干扰
    def outlineTitleList(self, outlinelist):
        self.outlinetitlelist = [onlyLetterAndNumber(x[1]) for x in outlinelist]

    # 判定标题是否在目录中，简单地相等，有时候还不行，因为有干扰字符串
    # 假设干扰字符串都有\r符号
    def isEletextInOutline(self, eletext):
        neweletext = eletext.replace('\n', '\r')
        splits = neweletext.split('\r')
        for split in splits:
            elecompact = onlyLetterAndNumber(split)
            if elecompact in self.outlinetitlelist:
                return True

        # 对于包含节小标题的，要特别特殊处理，即使部分字符串在目录中，也需要清理
        if isSmallTitle(eletext):
            elecompact = onlyLetterAndNumber(split)
            for title in self.outlinetitlelist:
                if elecompact in title:
                    return True

        return False

    # 根据目录将pdf拆分为小块
    def makeChunkByOutline(self, orioutlinelist=None, contentindex=None):
        import math
        from utils import splitList

        if orioutlinelist is None or len(orioutlinelist) == 0:
            return None

        outlinelist = orioutlinelist.copy()
        self.outlineTitleList(outlinelist)

        currelementindex = 0  # 指针，指向当前的elements
        lastsuccesselement = 0  # 上一次成功的目录查找
        elecount = len(self.elements)
        # 先跳过正文的目录
        if contentindex is not None:
            currelementindex = contentindex
            lastsuccesselement = contentindex

        # 查找每个目录对应的element的编号
        # First we search in the title list
        currtitleindex = 0
        lastsuccesstitle = 0
        titlecount = len(self.alltitles)
        lefttitleindexs = (
            []
        )  # the index of the outline which can't be found int the alltitles
        for index, outlineitem in enumerate(outlinelist):
            findelement = False
            while currtitleindex < titlecount:
                currtitle = self.alltitles[currtitleindex]
                nexttitletext = ""
                if currtitleindex < titlecount - 1:
                    nexttitletext = self.alltitles[currtitleindex + 1][2]
                if self.isidential(outlineitem[1], currtitle[2], nexttitletext):
                    if len(outlinelist[index]) <= 2:
                        outlinelist[index].append(currtitle[1])
                    else:
                        outlinelist[index][2] = currtitle[1]
                    findelement = True
                    lastsuccesstitle = currtitleindex
                    currtitleindex += 1
                    break

                currtitleindex += 1

            if not findelement:  # 如果找不到行，首先降低搜索要求，进行部分字符串搜索，并且降低匹配要求
                if outlineitem[0] == 1:  # 如果是一级标题，因为可能没有编号，所以需要降低匹配要求
                    currtitleindex = 0
                    compressoutline = compressDigital(outlineitem[1]).strip()
                    while currtitleindex < titlecount:
                        currtitle = self.alltitles[currtitleindex]
                        nexttitletext = ""
                        if currtitleindex < titlecount - 1:
                            nexttitletext = self.alltitles[currtitleindex + 1][3]
                        if self.isidential(compressoutline, currtitle[3], nexttitletext, threshold=80):
                            if len(outlinelist[index]) <= 2:
                                outlinelist[index].append(currtitle[1])
                            else:
                                outlinelist[index][2] = currtitle[1]
                            findelement = True
                            lastsuccesstitle = currtitleindex
                            currtitleindex += 1
                            break

                        currtitleindex += 1
                else:  # 不是一级编号，因为有明确地编号，可以直接搜索编号一致即可
                    currtitleindex = 0
                    titletag = isSmallTitle(outlineitem[1], sectiononly=True, rettaglevel=False, retnumber=True)
                    while currtitleindex < titlecount:
                        currtitle = self.alltitles[currtitleindex]
                        currtag = isSmallTitle(currtitle[2], sectiononly=True, rettaglevel=False, retnumber=True)
                        if titletag == currtag:
                            if len(outlinelist[index]) <= 2:
                                outlinelist[index].append(currtitle[1])
                            else:
                                outlinelist[index][2] = currtitle[1]
                            findelement = True
                            lastsuccesstitle = currtitleindex
                            currtitleindex += 1
                            break

                        currtitleindex += 1
                    pass
                pass

            if not findelement:  # 如果找不到行，则应该忽略这个目录
                currtitleindex = lastsuccesstitle
                lefttitleindexs.append(index)

        # 如果只查找标题，无法找到某个目录，则需要查找所有的elements
        if len(lefttitleindexs) > 0:
            for index, outlineitem in enumerate(outlinelist):
                if index not in lefttitleindexs:
                    continue

                findelement = False
                while currelementindex < elecount:
                    currelement = self.elements[currelementindex]
                    nextelementtext = ""
                    if currelementindex < elecount - 1:
                        nextelementtext = self.elements[currelementindex + 1]
                    # some title has two lines, the second line is not title type
                    if self.isidential(outlineitem[1], currelement, nextelementtext):
                        if len(outlinelist[index]) <= 2:
                            outlinelist[index].append(currelementindex)
                        else:
                            outlinelist[index][2] = currelementindex

                        findelement = True
                        lastsuccesselement = currelementindex
                        currelementindex += 1
                        lefttitleindexs.remove(index)
                        break
                    currelementindex += 1

                if not findelement:  # 如果找不到行，则应该忽略这个目录
                    currelementindex = lastsuccesselement

        # 删除没有对应内容的目录
        lefttitleindexs.sort(reverse=True)
        for leftindex in lefttitleindexs:
            nextindex = leftindex + 1
            leftlevel = outlinelist[leftindex][0]
            if leftindex < len(outlinelist) - 1:
                nextlevel = outlinelist[nextindex][0]
                # 如果当前标题的level比下个标题大，则允许没有内容（连续标题）
                if leftlevel < nextlevel:
                    continue
            # 否则弹出这个项
            outlinelist.pop(leftindex)

        # 目录找好后，开始查找内容
        prevelementindex = 0
        preoutlineindex = 0
        eletextcache = []  # 一摸一样的句子滤掉，因为很可能是页眉页脚，不产生实际的信息
        elecount = len(self.elements)
        for index, outlineitem in enumerate(outlinelist):
            contentstr = ""
            if len(outlineitem) < 3:  # 没有编号的，直接忽略
                continue
            elementindex = outlineitem[2]
            # 记录从第1个目录开始

            if prevelementindex == 0:
                prevelementindex = elementindex
                continue

            # 很多时候，尤其是chapter 1的标题，经常喜欢占两行，这里要特别处理下
            titleletext = self.elements[prevelementindex]
            titletag = self.findTagsInElement(titleletext, numberonly=True, titleonly=True)
            if prevelementindex + 1 < elementindex:
                for i in range(prevelementindex + 1, elementindex):
                    if i >= elecount:
                        continue

                    eletext = self.elements[i]
                    eletag = self.findTagsInElement(eletext, numberonly=True, titleonly=True)
                    eletext = self.cleanElementText(eletext)
                    if len(eletext) > 0:
                        if eletext in eletextcache:
                            continue
                        # 除去空行后，第1个同级别的，或者级别更低的标题，需要合并
                        if titletag is not None and eletag is not None and titletag >= eletag:
                            if '.' == outlinelist[preoutlineindex][1][-1]:
                                outlinelist[preoutlineindex][1] += ' ' + eletext
                            else:
                                outlinelist[preoutlineindex][1] += '. ' + eletext
                            self.outlineTitleList(outlinelist)
                            continue

                        # 排除和目录完全相同的字符串，这些最大可能是页眉页脚之类
                        if self.isEletextInOutline(eletext):
                            continue

                        contentstr = contentstr + eletext  # 使用pdf原来的回车，不再额外增加回车
                        eletextcache.append(eletext)

                        titletag = None  # if not part of title, then don't compare anymore

            if len(outlineitem) < 3:
                outlineitem.append(prevelementindex)

            contentstr = self.filterContent(contentstr)
            outlinelist[index - 1].append(contentstr)
            prevelementindex = elementindex
            preoutlineindex = index

        # 最后一段的处理
        if self.contentend is not None and prevelementindex + 1 < self.contentend:
            contentstr = ""
            for i in range(prevelementindex + 1, self.contentend):
                if i >= elecount:
                    continue

                eletext = self.elements[i]
                eletext = self.cleanElementText(eletext)
                if len(eletext) > 0:
                    if eletext in eletextcache:
                        continue

                    # 排除和目录完全相同的字符串，这些最大可能是页眉页脚之类
                    if self.isEletextInOutline(eletext):
                        continue

                    contentstr = contentstr + eletext
                    eletextcache.append(eletext)

            outlinelist[-1].append(contentstr)

        # split chunk if it is too large, because chatgpt has limit, we set length to 7500 chars
        # gpt has much more tokens support, so no need to split chunk
        '''for outlineitem in outlinelist:
            if len(outlineitem) < 4:
                continue
            contentstr = outlineitem[3]
            if len(contentstr) <= MAXSPLITCHARS:
                continue

            contentcount = len(contentstr)
            splitcount = math.ceil(contentcount / MAXSPLITCHARS)
            seperator = "\r"
            if "\r" in contentstr or "\n" in contentstr:
                splits = contentstr.splitlines()
            elif "." in contentstr or "。" in contentstr:
                splits = re.split("[.。]", contentstr)
                seperator = "."
            else:
                splits = contentstr.split(" ")
                seperator = ""

            resultlist = splitList(splits, splitcount)
            for index, result in enumerate(resultlist):
                newstr = seperator.join(result)
                if index == 0:
                    outlineitem[3] = newstr
                else:
                    outlineitem.append(newstr)
                pass'''

        if self.fakelasttitle:
            outlinelist.pop(-1)

        self.chunks = outlinelist
        return self.chunks
