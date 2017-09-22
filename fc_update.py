#!/usr/bin/env python3

import logging
import requests, bs4
import threading
import shelve
import sys, os, shutil, datetime, traceback
import argparse
import io, time
import collections

# LOG_LEVEL = logging.DEBUG
LOG_LEVEL = logging.INFO
LOG_DATE_FMT = "%b %d %H:%M:%S"
DB_NAME = "/tmp/fc_update/data.db"
JP_IMG_FILE = "cwm_ljp.gif"
JP_IMG_URL = "http://www.imocwx.com/cwm/cwm_ljp.gif"
CHUNK_SIZE = 100*1024
KEY_WG = "wg_data"
KEY_TIDE = "tide_data"
KEY_WEATHER = "weather_data"
TIDE_DATA_DAYS = 4
MSW_SITE = "http://magicseaweed.com/"
CWB_SITE = "http://www.cwb.gov.tw/"

SITE_CATEG_TWN = "twn"
SITE_CATEG_TWE = "twe"
SITE_CATEG_TWW = "tww"
SITE_CATEG_BALI = "bali"
SITE_CATEG_TW = [ SITE_CATEG_TWN, SITE_CATEG_TWE, SITE_CATEG_TWW ]
SITE_CATEG_ALL = [ SITE_CATEG_TWN, SITE_CATEG_TWE, SITE_CATEG_TWW, SITE_CATEG_BALI ]

SiteInfo = collections.namedtuple('SiteInfo', ('name', 'wg_url', 'tide_url', 'weather_url'))

# TW windguru: http://dracula0911.blogspot.tw/2013/11/blog-post.html
INFOS_MAP = {
    SITE_CATEG_TWN : [
        SiteInfo("honeymoonbay",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=174669",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/000204.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/1000204.htm"),
        SiteInfo("suao",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=167601",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/000203.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/1000203.htm"),
        SiteInfo("zhongjiao",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=167612",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/500027.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/6502700.htm")
    ],
    SITE_CATEG_TWE : [
        SiteInfo("donghe",
                 # wg_url = "http://old.windguru.cz/int/index.php?sc=473042",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=174509",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/001407.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/1001407.htm"),
        SiteInfo("yiwan",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=167746",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/001402.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/1001402.htm"),
        SiteInfo("fongbin",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=167744",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/001508.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/1001508.htm"),
        SiteInfo("papayastream",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=167745",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/001505.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/1001505.htm")
    ],
    SITE_CATEG_TWW : [
        SiteInfo("daan",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=179235",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/600011.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/6601100.htm"),
        SiteInfo("machang",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=360240",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/700033.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/6703300.htm"),
        SiteInfo("qijun",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=173865",
                 tide_url = "http://www.cwb.gov.tw/V7/forecast/fishery/Tidal30days/401000.htm",
                 weather_url = "http://www.cwb.gov.tw//V7/forecast/town368/3Hr/6403000.htm"),
    ],
    SITE_CATEG_BALI : [
        SiteInfo("canggu",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=208484",
                 tide_url = "http://magicseaweed.com/Canggu-Surf-Report/935/Tide/",
                 weather_url = ""),
        SiteInfo("sanur",
                 wg_url = "http://old.windguru.cz/int/index.php?sc=208480",
                 tide_url = "http://magicseaweed.com/Sanur-Surf-Report/1272/Tide/",
                 weather_url = "")
    ]
}

#################
##    Class    ##
#################

class DataFetcher(object):
    def __init__(self, url, cookie=''):
        self.url = url
        self.cookie = cookie

    def fetch(self):
        if not self.url:
            return ""

        resp = requests.get(self.url, cookies=self.cookie)
        resp.raise_for_status()
        resp.encoding = 'utf-8'

        data = []
        soup = bs4.BeautifulSoup(resp.text, "html.parser")

        return self._get_data(soup)

    def _get_data(self, soup):
        return ""

class WindGuruDataFetcher(DataFetcher):
    # Based on my display preference
    COOKIE = {
        '_ga': 'GA1.2.548425714.1489280472',
        '_gat': '1',
        'cookieconsent_dismissed': 'yes',
        'cuid': '3e9aa5c1f5e6c2d09e1710cd34f3dca9',
        'idu': '710029',
        'langc': 'en-',
        'nuid': 'c9e64acd664975d4ec262168f72044a7',
        'wg_cookie': '1|||||||||174509_174669||||0|_	'
    }

    def __init__(self, url):
        super(WindGuruDataFetcher, self).__init__(url, self.COOKIE)

    def _get_data(self, soup):
        tag = soup.select_one('div#div_wgfcst1')
        del tag['id']

        script = tag.select_one('script')
        del script['language']

        return str(tag)

class WeatherDataFetcher(DataFetcher):
    REMOVE_TR_IDX_7DAY = [ 5, 6, 7, 8, 9 ]
    REMOVE_TR_IDX_3HR = [ 4, 5, 6, 7, 9 ]

    @staticmethod
    def remove_empty_lines(string):
        return '\n'.join([ line for line in string.split('\n') if line.strip() != '' ])

    def _get_data(self, soup):
        rm_tr_idx = self.__get_rm_tr_idx()
        return self.__do_get_data(soup, rm_tr_idx)

    def __do_get_data(self, soup, rm_tr_idx):
        div = soup.select_one('.Forecast-box')
        tbl = div.select_one('table')

        del tbl['align']
        del tbl['height']
        del tbl['width']
        del tbl['border']

        for idx, tr in enumerate(div.select('tr')):
            if 0 == idx:
                tr['class'] = "tr-date"

            if idx in rm_tr_idx:
                tr.decompose()
            else:
                del tr['bgcolor']

        for img in div.select('img'):
            img['alt'] = "missing img"

        # font is obsolete, replace with span
        for font in div.select('font'):
            span = soup.new_tag('span')
            span.contents = font.contents
            span['style'] = "color: %s" % (font['color'])
            font.replace_with(span)

        return WeatherDataFetcher.remove_empty_lines(str(div))

    def __get_rm_tr_idx(self):
        if -1 == self.url.find("/3Hr/"):
            return self.REMOVE_TR_IDX_7DAY
        else:
            return self.REMOVE_TR_IDX_3HR

class MswTideDataFetcher(DataFetcher):
    def _get_data(self, soup):
        html = ""
        day = 0

        for div in soup.select('div.msw-tide-tables'):
            tag = div.select_one('table')

            for tr in tag.select('tr'):
                td = tr.select_one('td')
                if td.get_text() == "High":
                    cls = 'high-tide'
                elif td.get_text() == "Low":
                    cls = 'low-tide'
                else:
                    cls = ""
                tr['class'] = cls

            del tag['class']
            html += str(tag)

            day += 1
            if day == TIDE_DATA_DAYS:
                break

        return '\n<div class="tide-tbls tide-msw">%s</div>\n' % (html)

class CwbTideDataFetcher(DataFetcher):
    def _get_data(self, soup):
        html = final_html =""
        data1 = []
        data2 = []
        total_rows = 0
        total_days = TIDE_DATA_DAYS
        day = 0
        row = 0

        # td: 星期二, 大潮
        for tag in soup.select('td[rowspan]'):
            if -1 == tag.get_text().find("星期"):
                continue

            del tag['style']
            text = tag.get_text()
            idx = text.find('農曆')
            rowspan = int(tag['rowspan'])
            total_rows += rowspan
            html = '<td rowspan="%d">%s<br/>%s<br/>%s</td>' %(rowspan, text[0:idx], text[idx:], tag.next_sibling.get_text())
            data1.append((html, rowspan))

            day += 1
            if day == total_days:
                break

        # td: 乾潮, 10:51, 12cm
        for tag in soup.select('td'):
            if 0 <= tag.get_text().find("滿潮"):
                cls = "high-tide"
            elif 0 <= tag.get_text().find("乾潮"):
                cls = "low-tide"
            else:
                continue

            html = '<td>%s</td>' % (tag.get_text().strip())
            html += str(tag.next_sibling) + str(tag.next_sibling.next_sibling.next_sibling)
            data2.append((cls, html))

            row += 1
            if row == total_rows:
                break

        # compose final_html
        for html1, rowspan in data1:
            final_html += "<table><tbody>"

            for cls, html2 in data2[0:rowspan]:
                final_html += '<tr class="%s">%s</tr>' % (cls, html1 + html2)
                html1 = '' # clear content

            final_html += "</tbody></table>"
            data2 = data2[rowspan:]

        final_html = '\n<div class="tide-tbls tide-cwb">%s</div>\n' % (final_html)

        return final_html

class DatabaseUpdater(object):
    def __init__(self, categs):
        self.tgt_categs = categs
        self.lock = threading.Lock()
        self.threads = []

    def __del__(self):
        dirname = os.path.dirname(DB_NAME)
        shutil.rmtree(dirname)

    def run(self):
        check_to_create_parent_dir(DB_NAME)
        self.db = shelve.open(DB_NAME, flag='c', writeback=True)
        self.threads.append(start_thread(self.__fetch_jp_img))

        for categ in self.tgt_categs:
            if not categ in INFOS_MAP:
                continue

            for info in INFOS_MAP[categ]:
                logging.info("Fetch data for site [%s]." % (info.name))

                self.threads.append(start_thread(self.__fetch_wg_data, [info]))
                self.threads.append(start_thread(self.__fetch_tide_data, [info]))

                if info.weather_url:
                    self.threads.append(start_thread(self.__fetch_weather_data, [info]))

        join_all_threads(self.threads)
        self.db.close()

    def __fetch_jp_img(self):
        download_file(JP_IMG_URL, JP_IMG_FILE)

    def __fetch_wg_data(self, info):
        data = WindGuruDataFetcher(info.wg_url).fetch()
        logging.debug("wg_data: " + data)
        self.__update_db(info.name, KEY_WG, data)

    def __fetch_weather_data(self, info):
        data = WeatherDataFetcher(info.weather_url).fetch()

        logging.debug("weather_data: " + data)
        self.__update_db(info.name, KEY_WEATHER, data)

    def __fetch_tide_data(self, info):
        data = ""
        url = info.tide_url

        if -1 != url.find(CWB_SITE):
            data = CwbTideDataFetcher(url).fetch()
        elif -1 != url.find(MSW_SITE):
            data = MswTideDataFetcher(url).fetch()
        else:
            logging.error("Unknown tide url [%s]" % url)

        logging.debug("tide_data: " + data)
        self.__update_db(info.name, KEY_TIDE, data)

    def __update_db(self, site_name, key, data):
        self.lock.acquire()
        data_dict = self.db.setdefault(site_name, {})
        data_dict[key] = data
        self.lock.release()

class HtmlCreater(object):
    HTML_START = r'''
<!DOCTYPE html>
  <html lang="en">
    <head>
      <meta charset="utf-8"/>
	<title>Surf Forecast</title>
	<link rel="stylesheet" href="/css/wgstyle.min.css"/>
	<link rel="stylesheet" href="/css/style.css"/>
	<link rel="icon" href="/images/favicon.ico"/>
	<script src="/js/jquery.min.js"></script>
	<script src="/js/forecasts.min.js"></script>
	<script src="/js/wg_user_colors_json.js"></script>
	<!-- <script src="/js/jquery-scrolltofixed-min.js"></script> -->
	<script>
	    //<![CDATA[
var WgLang = {"legend":{"SMER":"Wind direction","TMP":"Temperature","WINDSPD":"Wind speed","MWINDSPD":"Modif. wind","APCP":"Rain (mm\/3h)","TCDC":"Cloud cover (%)","HTSGW":"Wave","WAVESMER":"Wave direction","RATING":"Windguru rating","PERPW":"Wave period (s)","APCP1":"Rain (mm\/1h)","GUST":"Wind gusts","SLP":"<span class=\"helpinfhpa\">*Pressure (hPa)<\/span>","RH":"Humidity (%)","FLHGT":"<span class=\"helpinffl\">*0\u00b0 isotherm (m)<\/span>","CDC":"Cloud cover (%)<br\/>high \/ mid \/ low","TMPE":"<span class=\"helpinftmp\">*Temperature <\/span>","WCHILL":"Wind chill","APCPs":"<span class=\"helpinfsnow\">*Precip. (mm\/3h)<\/span>","APCP1s":"<span class=\"helpinfsnow\">*Precip. (mm\/1h)<\/span>","WVHGT":"Wind wave","WVPER":"Wind wave per.(s)","WVDIR":"Wind wave dir.","SWELL1":"Swell","SWPER1":"Swell period (s)","SWDIR1":"Swell direction","SWELL2":"2.Swell","SWPER2":"2.Swell period (s)","SWDIR2":"2.Swell dir.","DIRPW":"Wave direction","WAVEDIR":"Wave direction"},"tooltip":{"TMPE":"Temperature at 2 meters above surface adjusted to real altitude of the spot. More info in Help\/FAQ section.","SLP":"Sea level pressure in hPa, values above 1000 hPa are printed <b>as x-1000<\/b>","FLHGT":"Freezing level height in meters","sst":"Sea surface temperature based on satellite data. Valid for oceans and large lakes, more info in help\/FAQ","APCP1s":"Precipitation in milimeters. Bold blue numbers indicate snowfall.","APCPs":"Precipitation in milimeters. Bold blue numbers indicate snowfall."},"dir":["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"],"weekday":["Su","Mo","Tu","We","Th","Fr","Sa"],"txt":{"archive":"Archive","tides":"Tides","detail":"Detail \/ Map","link":"Link","timezone":"Timezone","help":"Help","options":"Options","choose_m":"Choose wind modification","loading":"Loading forecast...","delayed":"12 hours delayed forecast. Latest MM5\/WRF forecasts are only available to Windguru PRO subscribers. <a href='help_index.php?sec=pro'>Click for more info.<\/a>","delayed_short":"12 hours delayed forecast. Latest MM5\/WRF forecasts are only available to Windguru PRO subscribers.","custom_onlypro":"MM5\/WRF forecasts for custom spots are only available to Windguru PRO users","lastupdated":"Last updated","nextexpected":"Next update expected","timeleft":"Time left"},"tab":{"forecast":"Forecast","graph":"<img src=\"\/images\/gricon.png\" width=\"15\" height=\"10\"\/>","2d":"2D","2d_t":"Temperature (0 ... 5000 m)","2d_w":"Wind (0 ... 5000 m)","2d_t_l":"Temperature (alt ... +2000 m)","2d_w_l":"Wind (alt ... +2000 m)","map":"Map","webcams":"Webcams","reports":"Wind reports","accommodation":"Accommodation","schools":"Schools\/Rentals","shops":"Shops","other":"Other...","directory":"Links","fcst_graph":"<img src=\"\/img\/gricon.png\"\/>","more":"<span class=\"butt-txt\">More<\/span>","statistic":"Statistics","archive":"Archive"},"units":{"kmh":"km\/h","mph":"mph","ms":"m\/s","msd":"m\/s","knots":"knots","bft":"Bft","c":"&deg;C","f":"&deg;F","m":"m","ft":"ft"},"maps":{"windspd":"Wind","t2m":"Temperature","press":"Pressure","tcdc_apcp3":"Rain \/ clouds","tcdc_apcp1":"Rain \/ clouds"},"mapsi":{"windspd":"wind","t2m":"temperature","press":"pressure","tcdc_apcp3":"precipitation","tcdc_apcp1":"precipitation"},"gmap":{"link_f":"Forecast","link_a":"Archive","link_d":"Detail","link_add":"Add to favourites","link_s":"Select"},"spotmenu":{"sel_zeme":"SELECT COUNTRY","sel_spot":"SELECT SPOT","num_spot":"spots","num_reg":"regions","num_zeme":"countries","sel_all":"ALL","qs_hint":"Type spot name (min. 3 characters)"},"langdir":{"dir":"int"}};
//]]>
    </script>
  </head>
  <body>
'''
    HTML_JP_IMG = '<img src="%s" id="jp_img" alt="missing image"/>\n' % ("/" + JP_IMG_FILE)
    HTML_NEXT_BTN = '<div id="next_btn" class="next_btn"></div>\n'
    HTML_BTNS_DIV = r'''<div class=button-grp>
<button id="upd_btn" class="custom_btn">Update Data</button>
<button id="weather_btn" class="custom_btn">Show Weather</button>
</div>'''
    HTML_END = r'''
    <script src="/js/main.js"></script>
    <script> Main(); </script>
  </body>
</html>'''

    def __init__(self, filename, categ):
        self.filename = filename
        self.categ = categ

    def run(self):
        check_to_create_parent_dir(self.filename)

        with io.open(self.filename, "w", encoding='utf-8') as fd, shelve.open(DB_NAME, 'r') as db:
            fd.write(self.HTML_START)
            self.__write_hidden_divs(fd)
            self.__write_content(fd, db)
            self.__write_buttons(fd)
            fd.write(self.HTML_END)

    def __write_hidden_divs(self, fd):
        fd.write('<div id="mask"></div>')
        fd.write('<div id="loading-icon"></div>')
        fd.write('<div id="site-categ">%s</div>' % (self.categ))

    def __write_content(self, fd, db):
        utc = datetime.datetime.utcnow()
        fd.write('<div class="last_upd_tm">%d</div>\n' % (utc.timestamp()))

        if self.categ in SITE_CATEG_TW:
            fd.write('<div class="img-with-btn">\n')
            fd.write(self.HTML_JP_IMG)
            fd.write(self.HTML_NEXT_BTN)
            fd.write('</div>\n')

        logging.info("jp_img download complete.")

        if not self.categ in INFOS_MAP:
            return

        for info in INFOS_MAP[self.categ]:
            logging.info("Writting data of [%s]" % (info.name))

            data = db[info.name]

            fd.write(data[KEY_WG])
            if KEY_WEATHER in data: fd.write(data[KEY_WEATHER])
            fd.write(data[KEY_TIDE])

    def __write_buttons(self, fd):
        fd.write(self.HTML_BTNS_DIV)


#########################
##    UTIL_FUCTIONS    ##
#########################

def start_thread(func, args=()):
    thread = threading.Thread(target=func, args=args)
    thread.start()

    return thread

def join_all_threads(threads):
    for thread in threads:
        thread.join()

def check_to_create_parent_dir(filepath):
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

def download_file(url, filepath):
    resp = requests.get(url)
    resp.raise_for_status()

    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    with open(filepath, "wb") as fd:
        for chunk in resp.iter_content(CHUNK_SIZE):
            fd.write(chunk)

################
##    MAIN    ##
################

def main():
    init_logger()
    (workdir, cleanup, categs) = parse_args()

    if workdir:
        os.chdir(workdir)

    if cleanup == True:
        do_cleanup()
        sys.exit(0)

    update_html_files(categs)

def init_logger(filename=None):
    if filename:
        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s',
                            datefmt=LOG_DATE_FMT, level=LOG_LEVEL)
    else:
        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s',
                            datefmt=LOG_DATE_FMT, level=LOG_LEVEL,
                            filename=filename)

def parse_args():
    parser = argparse.ArgumentParser(description="Generate a surf-forecast html files.")
    parser.add_argument("-w", "--workdir", default="", help="set working directory")
    parser.add_argument("-c", "--categ", default="",
                        choices=SITE_CATEG_ALL,
                        help="set location target (all will be updated if not set)")
    parser.add_argument("-C", "--cleanup", action="store_true", default=False,
                        help="cleanup all download content")

    args = parser.parse_args()
    categs = [ args.categ ] if args.categ else SITE_CATEG_ALL

    logging.info("args: [%s]" % (str(args)))

    return (args.workdir, args.cleanup, categs)

def do_cleanup():
    dirs = SITE_CATEG_ALL
    files = [ DB_NAME, JP_IMG_FILE ]

    logging.info("Cleanup dirs: %s" % ", ".join(dirs))

    for d in dirs:
        shutil.rmtree(d, ignore_errors=True)

    logging.info("Cleanup files: %s" % ", ".join(files))

    for f in files:
        try:
            os.remove(f)
        except:
            pass

def update_html_files(categs):
    db_updater = DatabaseUpdater(categs)
    db_updater.run()

    for categ in categs:
        filepath = os.path.join(categ, "index.html")
        filepath_tmp = filepath + ".tmp"

        HtmlCreater(filepath_tmp, categ).run()
        shutil.move(filepath_tmp, filepath)

        logging.info('File "%s" is updated.' % (filepath))


if __name__ == "__main__":
    main()
