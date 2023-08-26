"use strict"

// overriding console.log in production
if (!window.location.host.includes("5000")) {
	console.log = function(){};
}

function getCurWordChar() {
	if (flaskData.useTraditional) {
		return curWords[0].traditional;
	}
	else{
		return curWords[0].simplified;
	}
}

function checkStringIsChinese(str) { // yoinked
	let pattern = new RegExp("[\u4E00-\u9FA5]+");
	if (pattern.test(str)) {
		return true;
	}
	return false;
}

function addWord(wordToAdd = null, fromList = null) {
	if (flaskData.curUsername == null) {
		createTempNotification("Not logged in, cannot add words");
		return;
	}

	console.log("ADDING WORD!");

	let bodyStr = JSON.stringify({}) // no word (random word) by default

	if (wordToAdd != null) {
		bodyStr = JSON.stringify({wordToAdd: wordToAdd, fromList: fromList})
	}

	fetch("/api/addword", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: bodyStr,
	})
	.then((response) => response.json())
	.then((respData) => {
		logApiMessage("addword", respData);

		if (!respData.success) {
			createTempNotification(`Error - ${respData.message}`);
			return;
		}

		if (respData.listFinished) {
			createTempNotification(`List finished - no new words to add`);
			return;
		}

		createTempNotification(`Added word - ${respData.wordAdded}`);
	});	
}

function createTempNotification(notiText) {
	let newDiv = document.createElement("div");

	newDiv.classList.add("tempnotification");
	newDiv.classList.add("backgroundandbordered");
	newDiv.textContent = notiText;

	document.getElementById("tempnotifications").appendChild(newDiv);
}

function logApiMessage(apiRoute, respData) {
	console.log(`api response: ${apiRoute} - ${respData.message}`);
}

function updateQueryString(key, value, url) { // https://stackoverflow.com/a/11654596/3867506
    if (!url) url = window.location.href;
    let re = new RegExp("([?&])" + key + "=.*?(&|#|$)(.*)", "gi"),
        hash;

    if (re.test(url)) {
        if (typeof value !== 'undefined' && value !== null) {
            return url.replace(re, '$1' + key + "=" + value + '$2$3');
        } 
        else {
            hash = url.split('#');
            url = hash[0].replace(re, '$1$3').replace(/(&|\?)$/, '');
            if (typeof hash[1] !== 'undefined' && hash[1] !== null) {
                url += '#' + hash[1];
            }
            return url;
        }
    }
    else {
        if (typeof value !== 'undefined' && value !== null) {
            let separator = url.indexOf('?') !== -1 ? '&' : '?';
            hash = url.split('#');
            url = hash[0] + separator + key + '=' + value;
            if (typeof hash[1] !== 'undefined' && hash[1] !== null) {
                url += '#' + hash[1];
            }
            return url;
        }
        else {
            return url;
        }
    }
}

window.addEventListener('error', event => {
	createTempNotification(`Error: ${event.message}`);
});
