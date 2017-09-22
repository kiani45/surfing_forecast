
MIN_UPDATE_INTERVAL = 10;  /* 1 min */
CGI_TIMEOUT = 30000;         /* 30 sec */
WEATHER_BUTTON_TXT_SHOW = "Show Weather";
WEATHER_BUTTON_TXT_HIDE = "Hide Weather";
TW_SITE_ARRAY = [ "twn", "twe" ];

String.format = function() {
  var s = arguments[0];
  for (var i = 0; i < arguments.length - 1; i++) {
	var reg = new RegExp("\\{" + i + "\\}", "gm");
	s = s.replace(reg, arguments[i + 1]);
  }

  return s;
};

function Main() {
	loaded = true; /* For windguru */
	loadingIcon = $("#loading-icon");
	mask = $("#mask");
	siteCateg = $("#site-categ").text();

	var last_upd_tm = $(".last_upd_tm");

	lastUpdTm = parseInt(last_upd_tm.text()); /* UTC time */
	last_upd_tm.text(String.format("[{0}] - Last Update: {1}",
								   siteCateg, GetTimeStr(lastUpdTm)));
	last_upd_tm.show()

	$("#next_btn").attr("title", GetNextSite()).click(OnNextBtnClick);
	$("#upd_btn").click(OnUpdBtnClick);
	$("#weather_btn").click(OnWeatherBtnClick);
}

function GetUTCTime() {
    var now = new Date();
    return Math.floor((now.getTime() + now.getTimezoneOffset()*60000)/1000);
}

function GetTimeStr(utcTm) {
	var tm = utcTm*1000 - new Date().getTimezoneOffset()*60000;
	return new Date(tm).toString();
}

function Mask() {
	mask.show();
	loadingIcon.show();
}

function UnMask() {
	mask.hide();
	loadingIcon.hide();
}

function CheckLastUpdateTime() {
	var now = GetUTCTime();
	var nextUpdTm = lastUpdTm + MIN_UPDATE_INTERVAL;

	if (now < nextUpdTm) {
		var msg = String.format('Cannot update in {0} minute(s).',
								Math.ceil((nextUpdTm-now)/60));
		alert(msg);
		return false;
	}

	return true;
}

function GetNextSite() {
	var sites = TW_SITE_ARRAY;
	var idx = sites.indexOf(siteCateg);

	if (sites.length === ++idx) {
		idx = 0;
	}

	return sites[idx];
}

function OnNextBtnClick() {
	Mask();
	location.href = "/" + GetNextSite() + "/index.html"
}

function OnUpdBtnClick() {
	if (false === CheckLastUpdateTime()) {
		return;
	}

	var fnOk = function(data, sts, jqXHR) {
		window.scrollTo(0, 0);
		location.reload();
	};

	var fnErr = function(jqXHR, sts, err) {
		alert(err);
	};

	$.ajax({
		url: "/fc_update.php",
		data: {
			categ: siteCateg
		},
		beforeSend: Mask,
		success: fnOk,
		error: fnErr,
		complete: UnMask,
		timeout: CGI_TIMEOUT
	});
}

function OnWeatherBtnClick() {
	$(".Forecast-box").fadeToggle();

	$(this).text(function(idx, text) {
		return (WEATHER_BUTTON_TXT_SHOW === text) ?
			WEATHER_BUTTON_TXT_HIDE : WEATHER_BUTTON_TXT_SHOW;
	});

	window.scrollTo(0, document.body.scrollHeight);
}
