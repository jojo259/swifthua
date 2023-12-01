"use strict"

setCurStatusMessage("Loading...");

let lastMousePos = null;
let strokesList = [];
let curWords = [];
let curProficiency = 3;
let atChar = 0;
let wrongStrokes = 0;
let correctStrokes = 0;
let correctStrokesThisChar = 0;
let consecutiveWrongStrokes = 0;
let usedHint = false;
let curTestType = "pronounce";
let wordCompleted = false;
let charCompleted = false;

let gotStrokeHints = 0;
let tookTooLong = false;

let charDatas = {};

let onTouchScreen = false;

let lastGotWords = 0;

let needToPostVolume = false;

let curAudio = null;

let userStartedCardAt = Date.now();
let userLastInteraction = 0;
let notifyAudio = null;

let mouseDown = 0;

getNewWords();
setDailyStudyTimer();

class QueueManager {
	checkQueueTimeoutId = null;
	curQueueSize = 0;

	setCheckQueueTimeout(timeoutSecs) {
		clearTimeout(this.checkQueueTimeoutId);

		timeoutSecs = Math.min(timeoutSecs, 600)

		this.checkQueueTimeoutId = setTimeout(() => {return this.checkQueueSize()}, timeoutSecs * 1000)
	}

	checkQueueSize() {
		if (flaskData.curUsername == null){
			console.log("user is not logged in, returning");
			return;
		}

		console.log("CHECKING QUEUE SIZE!");

		let that = this;

		fetch("/api/getqueuesize", {
				method: "GET",
			}
		)
		.then((response) => response.json())
		.then((queueSizeData) => {
			logApiMessage("getqueuesize", queueSizeData);

			that.curQueueSize = queueSizeData["queuesize"];

			console.log("queue size: " + that.curQueueSize);

			// set page title (disabled)

			/*
			if (document.title.includes(" - ")) {
				document.title = document.title.split("-")[0] + `- (${curQueueSize})`
			}
			else {
				document.title += ` - (${curQueueSize})`
			}
			*/

			let oldQueueSize = parseInt(document.getElementById("queuesizenum").innerText);
			if (that.curQueueSize > oldQueueSize){
				getNewWords();
			}

			that.setQueueSizeNum(that.curQueueSize);

			let dueInHour = queueSizeData["dueinhour"];
			let dueInFourHours = queueSizeData["dueinfourhours"];
			let dueInTwelveHours = queueSizeData["dueintwelvehours"];
			let dueInDay = queueSizeData["dueintwentyfourhours"];

			document.getElementById("queuesizenum-hour").innerText = queueSizeData["dueinhour"];
			document.getElementById("queuesizenum-fourhours").innerText = queueSizeData["dueinfourhours"];
			document.getElementById("queuesizenum-twelvehours").innerText = queueSizeData["dueintwelvehours"];
			document.getElementById("queuesizenum-twentyfourhours").innerText = queueSizeData["dueintwentyfourhours"];

			// display queue element

			document.getElementById("queueinfo").removeAttribute("hidden");

			// timings

			let nextDue = queueSizeData["nextdue"];

			let nextDueSeconds = nextDue - Date.now() / 1000;

			console.log("next word due in " + Math.floor(nextDueSeconds) + "s");

			that.setCheckQueueTimeout(nextDueSeconds + 1);
		});
	}

	setQueueSizeNum(toNum) {
		this.curQueueSize = toNum;
		document.getElementById("queuesizenum").innerText = this.curQueueSize;
	}

	decrementQueueSizeNum() {
		this.setQueueSizeNum(this.curQueueSize - 1);
		if (this.curQueueSize <= 0) {
			createTempNotification("Queue finished for now!");
		}
	}
}
let queueManager = new QueueManager();
queueManager.setCheckQueueTimeout(0);

class StudyTimer {

	secondsThisCard = 0;
	secondsDailyTotal = 0;

	checkIfNeedToIncrementTimer() {
		if (document.getElementById("statusmessage").textContent != "Next word (click)") {
			if (Date.now() - userStartedCardAt < 5 * 1000) {
				this.incrementTimer();
			}
			else if (curTestType == "define" || curTestType == "pronounce") {
				doCanvasFeedback("#f90");
				tookTooLong = true;
			}
		}
	}

	incrementTimer() {
		this.secondsThisCard++;
		this.secondsDailyTotal++;

		this.updateTimerElem();
	}

	updateTimerElem() {
		let studyTimerDate = new Date(null);
		studyTimerDate.setSeconds(this.secondsDailyTotal);
		let studyTimerTruncated = studyTimerDate.toISOString().substr(11, 8);

		if (this.secondsDailyTotal < 3600) {
			studyTimerTruncated = studyTimerTruncated.substr(3, 5);
		}

		document.getElementById("studytimer").innerText = studyTimerTruncated;
	}
}
let studyTimer = new StudyTimer();
setInterval(function() {
	studyTimer.checkIfNeedToIncrementTimer();
}, 1000);

class Constants {
	volumeLevels = [0, 0.2, 1];
	prettyTimeStr = {"draw": "Draw", "define": "Define", "pronounce": "Pronounce", "tutorial": "New word"};

	secondsBetweenPlayQueueAudio = 300;
	idleSecondsForQueueAudio = 300;

	canvasDotSpeed = 15;
	canvasDotFps = 60;
}
let globalConstants = new Constants();

class CanvasDot {
	constructor(atStroke) {
		if (atStroke < 0 || atStroke > curWords[0].strokes[atChar].length - 1) {
			return;
		}

		let canvasDot = document.createElement("div");
		canvasDot.classList.add("canvas-dot");

		document.getElementById("canvas-container").appendChild(canvasDot);

		this.elem = canvasDot;
		this.stroke = curWords[0].strokes[atChar][atStroke];
		this.animDist = 0;

		this.doAnim();
	}

	doAnim() {
		let newX = 0;
		let newY = 0;

		let totalTraversedDist = 0;
		let curLineAtDist = 0;
		let atPoint = 0;
		let successfullyFound = false;
		for (let curPoint of this.stroke) {
			let nextPoint = this.stroke[atPoint + 1];
			if (atPoint == this.stroke.length - 1) {
				nextPoint = this.stroke[atPoint];
			}
			let distToNextPoint = getDist(curPoint[0], curPoint[1], nextPoint[0], nextPoint[1]);
			if (distToNextPoint == 0) {
				distToNextPoint = 0.1; // no infinities allowed...
			}
			if (totalTraversedDist + distToNextPoint > this.animDist) { // if we have now passed the point at which the dot is supposed to be
				// the dot must now be placed between curPoint and nextPoint
				curLineAtDist = totalTraversedDist - this.animDist;
				let atLineDist = curLineAtDist / distToNextPoint;
				
				// interpolate between the two points
				newX = curPoint[0] - (nextPoint[0] - curPoint[0]) * atLineDist;
				newY = curPoint[1] - (nextPoint[1] - curPoint[1]) * atLineDist;

				successfullyFound = true;
				break;
			}
			totalTraversedDist += distToNextPoint;

			atPoint++;
		}

		if (!successfullyFound) {
			this.elem.remove();
			return;
		}

		this.elem.style.left = (newX - 16) + "px";
		this.elem.style.top = (newY - 16) + "px";
		this.elem.style.opacity = Math.min((totalTraversedDist - curLineAtDist) / 50, (getLineLength(this.stroke) - (totalTraversedDist - curLineAtDist)) / 100); // transparency at start and end of stroke

		let that = this;

		setTimeout(function () {
			that.animDist += globalConstants.canvasDotSpeed / globalConstants.canvasDotFps * 25;
			that.doAnim();
		}, 1000 / globalConstants.canvasDotFps, that);
	}
}

function changeProficiency(toNum) {
	curProficiency = toNum;

	let normalColor = "#eee";
	let specialColors = ["#f00", "#f90", "#0f0"];

	for (let i = 1; i <= 3; i++) {
		if (i == toNum) {
			document.getElementById(`proficiencybutton-${i}`).style.color = specialColors[i - 1];
		}
		else{
			document.getElementById(`proficiencybutton-${i}`).style.color = normalColor;
		}
	}
}

function clearCanvasButton() {
	if (curTestType != "draw" && curTestType != "tutorial") {
		return;
	}
	
	console.log("clearing canvas from button");

	clearBackgroundCanvas();
	strokesList = [];
	consecutiveWrongStrokes = 0;

	hideCharNavButtons();
	document.getElementById("proficiencybuttons-container").setAttribute("hidden", "hidden");

	setCurStatusMessage(globalConstants.prettyTimeStr[curTestType]);

	updateFinishedChars(atChar);
}

function postVolume(newVolume) {
	console.log("POSTING VOLUME!");

	fetch("/api/setvolume", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			newvolume: newVolume,
		})
	})
	.then((response) => response.json())
	.then((data) => logApiMessage("setvolume", data));
}

function addWordButton() {
	addWord();
	getNewWords();
}

function getNewWordsButton() {
	if (flaskData.curUsername != null) {
		let curSeconds = Date.now() / 1000;
		if (curSeconds - lastGotWords > 5) {
			lastGotWords = curSeconds;
			getNewWords();
			createTempNotification("Manually refreshing word queue");
		}
		else{
			createTempNotification("Wait a moment");
		}
	}
	else{
		createTempNotification("Not logged in, cannot refresh queue");
	}
}

function changeVolumeButton() { // min volume is 0 (off), max volume is 2
	flaskData.userSettings.curVolume += 1;
	if (flaskData.userSettings.curVolume > 2) {
		flaskData.userSettings.curVolume = 0;
	}

	let volumeIds = ["sidebutton-volume-off", "sidebutton-volume-low", "sidebutton-volume-high"];

	let atNum = 0;
	for (const curId of volumeIds) {
		if (atNum == flaskData.userSettings.curVolume) {
			document.getElementById(curId).removeAttribute("hidden");
		}
		else{
			document.getElementById(curId).setAttribute("hidden", "hidden");
		}
		atNum++;
	}

	if (flaskData.curUsername != null) {
		needToPostVolume = true;
	}
}

function checkIfNeedToPostVolume() {
	if (needToPostVolume) {
		postVolume(flaskData.userSettings.curVolume);
		needToPostVolume = false;
	}
}
setInterval(checkIfNeedToPostVolume, 60 * 1000);

function charNav(navSide) {
	if (!(curTestType == "draw" || curTestType == "tutorial")) {
		return; // can only navigate between characters on draw or tutorial tests
	}
	if (!wordCompleted) {
		return; // can only navigate between characters if word has been completed
	}

	function boundAtChar() {
		if (atChar > getCurWordChar().length - 1) {
			atChar = getCurWordChar().length - 1;
		}
		if (atChar < 0) {
			atChar = 0;
		}
	}

	boundAtChar();

	let prevAtChar = atChar;
	atChar += navSide;
	
	boundAtChar();

	if (atChar != prevAtChar) {
		clearBackgroundCanvas();
		drawHanziSvg(curWords[0].svgdatas[atChar], 0, 99, 0, 0);
	}

	showAndUpdateCharNavButtons();
}

function fullHint() {
	console.log("showing full hint");

	if (curTestType == "draw" || curTestType == "tutorial") {
		clearBackgroundCanvas();
		clearDrawingCanvas();
		drawHanziSvg(curWords[0].svgdatas[atChar], 0, 0, 0, 99);

		usedHint = true;

		strokesList = [];
	}
	else if (curTestType == "pronounce") {
		playHanziAudio(getCurWordChar());
		goToWordEnd();
	}
	else if (curTestType == "define") {
		goToWordEnd();
	}
}

function playWordAudio() {
	playHanziAudio(getCurWordChar());
}

function updateFinishedChars(numFinished) {
	let finishedCharsStr = "";

	for (let i = 0; i < numFinished; i++) {
		finishedCharsStr += getCurWordChar().charAt(i);
	}

	for (let i = 0; i < getCurWordChar().length - numFinished; i++) {
		finishedCharsStr += "__ ";
	}

	document.getElementById("curword-finishedchars").textContent = finishedCharsStr;
	document.getElementById("curword-finishedchars").title = finishedCharsStr;
}

function parseWordDatas(wordDatas) {
	let parsedWordDatas = [];
	for (let u = 0; u < wordDatas.length; u++) {
		let wordData = wordDatas[u];

		for (let p = 0; p < wordData.strokes.length; p++) {
			let curChar = wordData.strokes[p];

			for (let o = 0; o < curChar.length; o++) {
				let curStroke = curChar[o];
				let lastPos = [null, null];

				let canvas = document.getElementById("canvas-background");
				let ctx = canvas.getContext("2d");
				ctx.lineWidth = 4;

				for (let i = 0; i < curStroke.length; i++) {
					wordData.strokes[p][o][i] = [curStroke[i][0] / 1024 * 480, (1024 - (curStroke[i][1] + 124)) / 1024 * 480];

					if (false && lastPos[0] != null && u == 0 && p == 0) { // draw stroke data for debugging
						ctx.strokeStyle = "#ccc";
						ctx.beginPath();
						ctx.moveTo(lastPos[0], lastPos[1]);
						ctx.lineTo(wordData.strokes[p][o][i][0], wordData.strokes[p][o][i][1]);
						ctx.stroke();

						ctx.strokeStyle = "#f00";
						ctx.beginPath();
						ctx.arc(wordData.strokes[p][o][i][0], wordData.strokes[p][o][i][1], 4, 0, 2 * Math.PI);
						ctx.stroke();

						lastPos = wordData.strokes[p][o][i];
					}
				}
			}
		}
		parsedWordDatas[u] = wordData;
	}

	console.log(wordDatas);

	parsedWordDatas = parsedWordDatas.filter(function(elem) { // yoinked
		if (curWords.length > 0) {
			return elem.simplified != getCurWordChar() && elem.traditional != getCurWordChar();
		}
		return true;
	});

	if (curWords.length > 0) {
		parsedWordDatas.unshift(curWords[0]);

		if (parsedWordDatas[0].simplified == parsedWordDatas[1].simplified) {
			parsedWordDatas.shift();
		}
	}
	
	if (curWords.length == 0) {
		curWords = parsedWordDatas;

		clearBackgroundCanvas();
		clearDrawingCanvas();

		setCurTestType();

		initCurTest();
	}
	else{
		curWords = parsedWordDatas;
	}

	console.log("finished getting new words");

	logCurrentQueue();
}

function initCurTest() {
	setCurStatusMessage(globalConstants.prettyTimeStr[curTestType]);

	cacheAudio();

	if(curTestType == "draw") {
		setCurWordData(curWords[0]["pinyin"], curWords[0]["english"]);
		updateFinishedChars(0);
	}
	else if (curTestType == "pronounce") {
		if (flaskData.userSettings.pronounceHard) {
			setCurWordData("", "");
		}
		else{
			setCurWordData("", curWords[0]["english"]);
		}

		updateFinishedChars(99);
		drawWord();
	}
	else if (curTestType == "define") {
		if (flaskData.userSettings.defineHard) {
			setCurWordData("", "");
		}
		else{
			setCurWordData(curWords[0]["pinyin"], "");
		}

		updateFinishedChars(99);
		drawWord();
	}
	else if (curTestType == "tutorial") {
		setCurWordData(curWords[0]["pinyin"], curWords[0]["english"]);

		updateFinishedChars(99);

		drawHanziSvg(curWords[0].svgdatas[atChar], 0, 0, 0, 1); // draw first stroke
		new CanvasDot(correctStrokesThisChar);
	}
}

function setCurTestType() {
	curTestType = curWords[0].testtype
	console.log(`set to ${curTestType} test`);
}

function hideWordInfo() {
	document.getElementById("wordinfobox").setAttribute("hidden", "hidden");
}

function showWordInfo() {

	//display test type

	document.getElementById("wordinfo-testtype").textContent = globalConstants.prettyTimeStr[curTestType];

	// display from lists

	if (flaskData.curUsername != null) {
		let fromListsStr = "";

		if (curWords[0].lists != null) {
			curWords[0].lists.forEach(function(curList) {
				fromListsStr += curList + " ";
			})
		}
		if (fromListsStr == "") {
			fromListsStr += "?";
		}

		document.getElementById("wordinfo-fromlists").textContent = fromListsStr;
		document.getElementById("wordinfo-fromlists").title = fromListsStr;
	}
	else{
		document.getElementById("wordinfo-fromlists").textContent = "hsk-1";
	}

	// display due
	
	if (flaskData.curUsername != null) {
		if (curTestType == "tutorial") {
			document.getElementById("wordinfo-due").textContent = "?";
		}
		else{
			document.getElementById("wordinfo-due").textContent = curWords[0].prettydue;
		}
	}
	else{
		document.getElementById("wordinfo-due").textContent = "?";
	}

	// display word strength

	if (flaskData.curUsername != null) {
		let curStrength = Math.floor(curWords[0].wordstrength);
		if (curTestType == "tutorial") {
			curStrength = "?";
		}
		document.getElementById("wordinfo-wordstrength").textContent = curStrength;

		if (curStrength >= 13 || curStrength == "?") {
			document.getElementById("wordinfo-wordstrength").style.color = "green";
		}
		else if (curStrength >= 7) {
			document.getElementById("wordinfo-wordstrength").style.color = "orange";
		}
		else{
			document.getElementById("wordinfo-wordstrength").style.color = "red";
		}
	}
	else{
		document.getElementById("wordinfo-wordstrength").innerHTML = "<a href='/login'>Login to save stats</a>"; // switch to in-code HTML construction to avoid potential future XSS?
		document.getElementById("wordinfo-wordstrength").style.color = "red"; // does not work due to link
	}

	// display simplified / traditional

	let curWordSimplified = curWords[0].simplified;
	let curWordTraditional = curWords[0].traditional;
	if (curWordSimplified == curWordTraditional) {
		document.getElementById("wordinfo-simplifiedtraditional").textContent = curWords[0].simplified + " (same)";
	}
	else{
		document.getElementById("wordinfo-simplifiedtraditional").textContent = curWords[0].simplified + " / " + curWords[0].traditional;
	}

	document.getElementById("wordinfobox").removeAttribute("hidden");
}

function logCurrentQueue() {
	let logStr = `Current queue (${curWords.length}): `;

	for (let i = 0; i < curWords.length - 0; i++) {
		logStr += curWords[i].simplified + " ";
	}

	console.log(logStr);
}

function getNewWords() {
	console.log("GETTING NEW WORDS!");

	fetch("/api/getwords", {
		method: "GET",
	})
	.then((response) => response.json())
	.then((wordDatas) => {
		logApiMessage("getwords", wordDatas);
		parseWordDatas(wordDatas.words);
	});
}

function setDailyStudyTimer() {
	console.log("SETTING DAILY STUDY TIMER!");

	fetch("/api/getdailystudytime", {
		method: "GET",
	})
	.then((response) => response.json())
	.then((respData) => {
		logApiMessage("getdailystudytime", respData);
		studyTimer.secondsDailyTotal = respData.seconds;
		studyTimer.updateTimerElem();
	});
}

function userCompletedWord(completedWord, wordProficiency) {
	console.log(`SENDING USER COMPLETED WORD! ${completedWord} ${curTestType} ${wordProficiency}`);

	if (flaskData.curUsername != null && curWords[0]["due"] < Date.now() / 1000) {
		queueManager.decrementQueueSizeNum();
	}

	fetch("/api/completedword", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			completedword: completedWord,
			wordproficiency: wordProficiency,
			testtype: curTestType,
			extrastudytime: studyTimer.secondsThisCard
		})
	})
	.then((response) => response.json())
	.then((respData) => {
		logApiMessage("completedword", respData);
		queueManager.setCheckQueueTimeout(1);
		checkIfNeedNewWords();

		if (flaskData.curUsername == null) {
			setTimeout(function(){createTempNotification("Login to save stats")}, 1000);
		}
	})
	.catch((error) => {
		createTempNotification(`Sending completed word failed: ${error.message}`);
	});
}

function checkIfNeedNewWords() {
	if (curWords.length <= 4) {
		console.log("queue too short");
		getNewWords();
	}
}

function clearBackgroundCanvas() {
	let backgroundCanvas = document.getElementById("canvas-background");
	let backgroundCtx = backgroundCanvas.getContext("2d");

	backgroundCtx.clearRect(0, 0, backgroundCanvas.width, backgroundCanvas.height);

	backgroundCtx.fillStyle = "#282828";
	backgroundCtx.fillRect(0, 0, backgroundCanvas.width, backgroundCanvas.height);

	// background lines
	backgroundCtx.strokeStyle = "#333";

	backgroundCtx.lineWidth = 4;

	backgroundCtx.beginPath();

	backgroundCtx.moveTo(0, 0);
	backgroundCtx.lineTo(480, 480);
	backgroundCtx.stroke();

	backgroundCtx.moveTo(480, 0);
	backgroundCtx.lineTo(0, 480);
	backgroundCtx.stroke();

	backgroundCtx.closePath();

	backgroundCtx.beginPath();

	backgroundCtx.moveTo(0, 240);
	backgroundCtx.lineTo(480, 240);
	backgroundCtx.stroke();

	backgroundCtx.moveTo(240, 0);
	backgroundCtx.lineTo(240, 480);
	backgroundCtx.stroke();

	backgroundCtx.closePath();
}

function clearDrawingCanvas() {
	let canvas = document.getElementById("canvas-draw");
	let ctx = canvas.getContext("2d");
	ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function updateUserLastInteraction() {
	userLastInteraction = Date.now() / 1000;
}
updateUserLastInteraction();

function playNotifyAudio() {
	console.log("playing notify audio");

	if (flaskData.userSettings.curVolume > 0) {
		if (notifyAudio == null) {
			notifyAudio = new Audio("/static/sounds/notify.mp3");
		}

		notifyAudio.volume = globalConstants.volumeLevels[flaskData.userSettings.curVolume];

		var resp = notifyAudio.play();

		if (resp!== undefined) {
			resp.then(_ => {
				
			}).catch(error => {
				console.log("playing notify audio failed, probably user has to interact with the DOM");
			});
		}
	}
}

function checkIfNeedToPlayQueueAudio() {
	if (queueManager.curQueueSize >= 12) {
		if (Date.now() / 1000 - userLastInteraction > globalConstants.idleSecondsForQueueAudio) {
			playNotifyAudio();
		}
	}
}

if (flaskData.userSettings.playQueueAudio) {
	console.log("enabled playing queue audio")
	setInterval(checkIfNeedToPlayQueueAudio, globalConstants.secondsBetweenPlayQueueAudio * 1000);
}

function cacheAudio() { // more like pre-fetching not caching
	curAudio = new Audio(`https://pinyin-word-api.vercel.app/api/audio/${getCurWordChar()}`);
}

function playHanziAudio(hanziTo) {
	if (flaskData.userSettings.curVolume > 0) {
		let theAudio = null;
		if (curAudio != null) {
			theAudio = curAudio;
		}
		else{
			theAudio = new Audio(`https://pinyin-word-api.vercel.app/api/audio/${hanziTo}`);
		}

		theAudio.volume = globalConstants.volumeLevels[flaskData.userSettings.curVolume];

		theAudio.play();
	}
}

function drawInlineSVG(svgElement, ctx, callback) { // yoinked
	let svgURL = new XMLSerializer().serializeToString(svgElement);
	let img = new Image();
	img.onload = function() {
		ctx.drawImage(this, 0, 0);
		callback();
	}
	img.src = "data:image/svg+xml; charset=utf8, " + encodeURIComponent(svgURL);
}

function drawHanziSvg(charSvgData, drawStrokesFrom, drawStrokesTo, hintStrokesFrom, hintStrokesTo, multiCharsPos, multiCharsTotal){ // mostly yoinked
	let target = document.getElementById("canvas-background");

	let ctx = target.getContext("2d");

	target.textContent = null;

	// initialize svg

	let svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
	svg.style.width = "480px";
	svg.style.height = "480px";
	target.appendChild(svg);
	let group = document.createElementNS("http://www.w3.org/2000/svg", "g");

	// if multiple chars being drawn then calculate actual positions

	let drawWidth = 480, drawHeight = 480;
	if (multiCharsPos != null && multiCharsTotal != null) {
		drawWidth = (120 * multiCharsPos + 120) * 2 - (multiCharsTotal - 1) * 120;
		drawHeight = 120;

		svg.setAttribute("transform", "translate(0, 180)"); // transform downwards
	}
	
	let transformData = HanziWriter.getScalingTransform(drawWidth, drawHeight);
	group.setAttributeNS(null, "transform", transformData.transform);
	svg.appendChild(group);

	let atStroke = 0;
	charSvgData.forEach(function(strokePath) {
		let strokeCol = null;

		// set color based on real stroke vs hint stroke

		if (atStroke >= drawStrokesFrom && atStroke < drawStrokesTo) {
			strokeCol = "#eee";
		}
		else if (atStroke >= hintStrokesFrom && atStroke < hintStrokesTo) {
			strokeCol = "#555";
		}

		atStroke++;

		if (strokeCol == null) {
			return;
		}

		let path = document.createElementNS("http://www.w3.org/2000/svg", "path");

		path.setAttributeNS(null, "d", strokePath);
		path.style.fill = strokeCol;

		group.appendChild(path);
	});

	drawInlineSVG(document.querySelector("svg"), ctx, function(){});
}

function getDist(x1, y1, x2, y2){ // yoinked probably
	return Math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2);
}

function getLineLength(ofLine) {
	let lineLength = 0;
	for (let i = 1; i < ofLine.length; i++) {
		lineLength += getDist(ofLine[i - 1][0], ofLine[i - 1][1], ofLine[i][0], ofLine[i][1]);
	}
	return lineLength;
}

function getBearing(x1, y1, x2, y2){ // yoinked
	return ( ( ( -(Math.atan2((x1-x2),(y1-y2))*(180/Math.PI)) % 360) + 360) % 360);
}
function getStrokeBearings(strokePoints) {
	let strokeBearings = [];
	for (let o = 0; o < strokePoints.length - 1; o++) {
		let curPoint = strokePoints[o];
		let nextPoint = strokePoints[o + 1];
		let curBearing = getBearing(curPoint.x, curPoint.y, nextPoint.x, nextPoint.y);
		strokeBearings.push(curBearing);
	}
	return strokeBearings;
}

function getCanvasMousePos(event) { // somewhat yoinked
	let canvas = document.getElementById("canvas-draw");
	let rect = canvas.getBoundingClientRect();

	let mousePos = null;

	if (event.type == "mousedown" || event.type == "mouseup" || event.type =="mousemove") {
		mousePos = {
			x: event.clientX - rect.left,
			y: event.clientY - rect.top
		};
	}
	else if (event.type == "touchstart" || event.type == "touchmove") {
		mousePos = {
			x: event.touches[0].clientX - rect.left,
			y: event.touches[0].clientY - rect.top
		};
	}
	else if (event.type == "touchend") {
		mousePos = {
			x: event.changedTouches[0].clientX - rect.left,
			y: event.changedTouches[0].clientY - rect.top
		};
	}
	else{
		console.log(event);
		return null;
	}

	return mousePos;
}

function doDraw(event) {
	if (!mouseDown) {
		return; // mouse is not down, no need to draw (should never trigger probably)
	}

	// check if cannot get canvas or event for some reason

	let canvas = document.getElementById("canvas-draw");

	if (!(canvas.getContext && event)) {
		console.log("failed to get canvas or event in doDraw")
		return;
	}

	// get things

	let ctx = canvas.getContext("2d");

	let mousePos = getCanvasMousePos(event);

	// calculate how far mouse has moved

	let lastPoint = strokesList[strokesList.length - 1][strokesList[strokesList.length - 1].length - 1];
	let dist = getDist(mousePos.x, mousePos.y, lastPoint.x, lastPoint.y);

	// if mouse has barely moved then just ignore

	if (dist < 1) {
		return;
	}

	// if mouse has moved far enough then add current position to list of strokes

	if (dist > 8) {
		strokesList[strokesList.length - 1].push(mousePos);
	}

	// if last mouse pos is null then just set it to current mouse pos (avoids errors and effectively only causes an off-by-one error)

	if (lastMousePos == null) {
		lastMousePos = getCanvasMousePos;
	}

	// draw

	let drawLineWidth = 16;

	ctx.beginPath();
	ctx.arc(lastMousePos.x, lastMousePos.y, drawLineWidth / 2, 0, 2 * Math.PI, false);
	ctx.fillStyle = "#eee";
	ctx.fill();

	ctx.strokeStyle = "#eee";
	ctx.beginPath();
	ctx.lineWidth = drawLineWidth;
	ctx.moveTo(lastMousePos.x, lastMousePos.y);
	ctx.lineTo(mousePos.x, mousePos.y);
	ctx.stroke();
}

function evalStroke() {
	if (mouseDown == 0) {
		return;
	}
	let lastStroke = strokesList[strokesList.length-1];

	if (lastStroke.length < 2) {
		clearDrawingCanvas();
		console.log("stroke too short, returning");
		strokesList.splice(strokesList.length - 1, 1);
		return;
	}

	// remove extraneous points (same logic is used when the stroke is being created with perhaps different value)
	// so probably totally unnecessary; *just to be safe
	for (let o = lastStroke.length - 2; o > 0; o--) {
		let curPoint = lastStroke[o];
		let prevPoint = lastStroke[o + 1];

		let dist = Math.sqrt((curPoint.x - prevPoint.x) ** 2 + (curPoint.y - prevPoint.y) ** 2);

		if (dist < 8) {
			lastStroke.splice(o, 1);
		}
	}

	clearDrawingCanvas();

	let canvas = document.getElementById("canvas-draw");
	let ctx = canvas.getContext("2d");

	// eval stroke initial data

	let curCharStroke = curWords[0].strokes[atChar][strokesList.length - 1];

	let userStrokeFirstPoint = lastStroke[0];
	let userStrokeMidPoint = lastStroke[Math.floor(lastStroke.length / 2) - 1];
	let userStrokeLastPoint = lastStroke[lastStroke.length - 1];

	let charStrokeFirstPoint = curCharStroke[0];
	let charStrokeMidPoint = curCharStroke[Math.floor(curCharStroke.length / 2) - 1];
	let charStrokeLastPoint = curCharStroke[curCharStroke.length - 1];
	
	let userStrokeSecondToLastPoint = lastStroke[lastStroke.length - 2];
	let charStrokeSecondToLastPoint = curCharStroke[curCharStroke.length - 2];
	let overshotMult = 16;
	let overshotPoint = {x: userStrokeLastPoint.x + (userStrokeLastPoint.x - userStrokeSecondToLastPoint.x) * overshotMult, y: userStrokeLastPoint.y + (userStrokeLastPoint.y - userStrokeSecondToLastPoint.y) * overshotMult};

	let firstPointDist = getDist(userStrokeFirstPoint.x, userStrokeFirstPoint.y, charStrokeFirstPoint[0] , charStrokeFirstPoint[1]);
	let midPointDist = getDist(userStrokeMidPoint.x, userStrokeMidPoint.y, charStrokeMidPoint[0] , charStrokeMidPoint[1]);
	let lastPointDist = getDist(userStrokeLastPoint.x, userStrokeLastPoint.y, charStrokeLastPoint[0] , charStrokeLastPoint[1]);
	let overshotDist = getDist(overshotPoint.x, overshotPoint.y, charStrokeLastPoint[0] , charStrokeLastPoint[1]);

	let userOverallStrokeBearing = getBearing(userStrokeFirstPoint.x, userStrokeFirstPoint.y, userStrokeLastPoint.x, userStrokeLastPoint.y);
	let charOverallStrokeBearing = getBearing(charStrokeFirstPoint[0], charStrokeFirstPoint[1], charStrokeLastPoint[0], charStrokeLastPoint[1]);

	let userLastStrokeBearing = getBearing(userStrokeSecondToLastPoint.x, userStrokeSecondToLastPoint.y, userStrokeLastPoint.x, userStrokeLastPoint.y);
	let charLastStrokeBearing = getBearing(charStrokeSecondToLastPoint[0], charStrokeSecondToLastPoint[1], charStrokeLastPoint[0], charStrokeLastPoint[1]);
	
	let overallBearingDiff = Math.min(Math.abs(userOverallStrokeBearing - charOverallStrokeBearing), Math.abs((userOverallStrokeBearing + 360) - charOverallStrokeBearing), Math.abs((userOverallStrokeBearing - 360) - charOverallStrokeBearing));
	let lastStrokeBearingDiff = Math.min(Math.abs(userLastStrokeBearing - charLastStrokeBearing), Math.abs((userLastStrokeBearing + 360) - charLastStrokeBearing), Math.abs((userLastStrokeBearing - 360) - charLastStrokeBearing));

	// calculate stroke lengths

	let userStrokeLen = getLineLength(lastStroke.map(x => [x.x, x.y]));
	let charStrokeLen = getLineLength(curCharStroke);

	let strokeLenDiff = Math.abs(userStrokeLen - charStrokeLen);

	// eval stroke logic

	let correctStroke = true;

	if (!(firstPointDist < 200 && midPointDist < 300 && (lastPointDist < 200 || overshotDist < 200))) {
		console.log("stroke wrong: points");
		correctStroke = false;
	}

	if (!(overallBearingDiff < 90 && lastStrokeBearingDiff < 90)) {
		console.log("stroke wrong: bearings");
		correctStroke = false;
	}

	if (!(strokeLenDiff < charStrokeLen / 1 || (charStrokeLen < 120 && strokeLenDiff < 120))) {
		console.log("stroke wrong: length");
		correctStroke = false;
	}

	//console.log({"strokeData":{firstPointDist: firstPointDist, midPointDist: midPointDist, lastPointDist: lastPointDist, overshotDist: overshotDist, overallBearingDiff: overallBearingDiff, lastStrokeBearingDiff: lastStrokeBearingDiff, strokeLenDiff: strokeLenDiff}});

	if (!correctStroke) {
		wrongStrokes += 1;
		consecutiveWrongStrokes += 1;

		strokesList.splice(strokesList.length - 1, 1);

		if (consecutiveWrongStrokes > 2) {
			gotStrokeHints += 1;
			drawHanziSvg(curWords[0].svgdatas[atChar], 0, 0, strokesList.length, strokesList.length + 1);
			new CanvasDot(correctStrokesThisChar);
		}

		doCanvasFeedback("#f00");

		return;
	}

	// stroke is correct

	consecutiveWrongStrokes = 0;
	correctStrokes += 1;
	correctStrokesThisChar += 1;

	drawHanziSvg(curWords[0].svgdatas[atChar], strokesList.length - 1, strokesList.length, 0, 0);

	// if current test type is tutorial then draw next stroke

	if (curTestType == "tutorial") {
		setTimeout(function() {
			drawHanziSvg(curWords[0].svgdatas[atChar], 0, 0, strokesList.length, strokesList.length + 1);
		}, 100)
		new CanvasDot(correctStrokesThisChar);
	}

	if (strokesList.length == curWords[0].strokes[atChar].length) {
		console.log("NEXT CHAR!");
		setCurStatusMessage("Next character (click)");
		charCompleted = true;

		correctStrokesThisChar = 0;
		
		if (atChar + 1 > curWords[0].strokes.length - 1 || wordCompleted){ // finished all chars
			console.log("FINISHED WORD!");

			wordCompleted = true;
			updateFinishedChars(99);
			showWordInfo();
			showAndUpdateCharNavButtons();
			playHanziAudio(getCurWordChar());
			setCurStatusMessage("Next word (click)");

			if (curTestType == "draw") {
				document.getElementById("proficiencybuttons-container").removeAttribute("hidden");
			}

			// set proficiency based on hints and stroke hints used
			
			if (usedHint) {
				changeProficiency(1);
			}
			else if (gotStrokeHints > 1) {
				changeProficiency(1);
			}
			else if (gotStrokeHints == 1) {
				changeProficiency(2);
			}
			else{
				changeProficiency(3);
			}
		}
		else if (curTestType == "draw") {
			updateFinishedChars(atChar + 1);
		}
	}
}

function hideCharNavButtons() {
	document.getElementById("charnavbutton-left").setAttribute("hidden", "hidden");
	document.getElementById("charnavbutton-right").setAttribute("hidden", "hidden");
}

function showAndUpdateCharNavButtons() { // better name?
	hideCharNavButtons();

	if (atChar > 0) {
		document.getElementById("charnavbutton-left").removeAttribute("hidden");
	}
	if (atChar < curWords[0].strokes.length - 1) {
		document.getElementById("charnavbutton-right").removeAttribute("hidden");
	}
}

function drawWord() {
	if (getCurWordChar().length > 4) {
		console.log("word too long to draw properly");
	}

	for (let i = 0; i < getCurWordChar().length; i++) {
		drawHanziSvg(curWords[0].svgdatas[i], 0, 99, 0, 0, i + 1, getCurWordChar().length);
	}
}

function goToNextWord() {
	userCompletedWord(getCurWordChar(), curProficiency);

	curWords = curWords.slice(1);
	atChar = 0;
	strokesList = [];
	usedHint = false;
	gotStrokeHints = 0;
	tookTooLong = false;
	wordCompleted = false;
	charCompleted = false;
	wrongStrokes = 0;
	correctStrokes = 0;
	correctStrokesThisChar = 0;
	consecutiveWrongStrokes = 0;
	userStartedCardAt = Date.now();
	studyTimer.secondsThisCard = 0;

	clearBackgroundCanvas();
	clearDrawingCanvas();

	document.getElementById("proficiencybuttons-container").setAttribute("hidden", "hidden");
	hideCharNavButtons();
	hideWordInfo();

	setCurTestType();

	initCurTest();
}

function setCurWordData(setPinyin, setDefinition) {
	if (setPinyin != undefined) {
		document.getElementById("curword-pinyin").innerText = setPinyin;
		document.getElementById("curword-pinyin").title = setPinyin;
	}

	if (setDefinition != undefined) {
		document.getElementById("curword-definition").innerText = setDefinition;
		document.getElementById("curword-definition").title = setDefinition;
	}
}

function setCurStatusMessage(setStatus) {
	document.getElementById("statusmessage").innerText = setStatus;
}

function doCanvasFeedback(showColor) {
	let canvasContainerElem = document.getElementById("canvas-container");
	canvasContainerElem.style.outline = `2px solid ${showColor}`;
	setTimeout(function() {
		canvasContainerElem.style.outline = "";
	}, 250);
}

function goToWordEnd() {
	wordCompleted = true;
	if(curTestType == "pronounce") {
		changeProficiency(3);

		playHanziAudio(getCurWordChar());

		setCurWordData(curWords[0]["pinyin"], curWords[0]["english"]);

		document.getElementById("proficiencybuttons-container").removeAttribute("hidden");
		document.getElementById("statusmessage").textContent = "Next word (click)";
		wordCompleted

		showWordInfo();
	}
	else if (curTestType == "define") {
		changeProficiency(3);

		playHanziAudio(getCurWordChar());

		setCurWordData(curWords[0]["pinyin"], curWords[0]["english"]);

		document.getElementById("proficiencybuttons-container").removeAttribute("hidden");
		setCurStatusMessage("Next word (click)");

		showWordInfo();
	}
	else if (curTestType == "tutorial") {
		changeProficiency(3);

		playHanziAudio(getCurWordChar());

		document.getElementById("proficiencybuttons-container").removeAttribute("hidden");

		setCurStatusMessage("Next word (click)");
	}

	if (tookTooLong && (curTestType == "define" || curTestType == "pronounce")) {
		changeProficiency(2);
	}
}

function goToNextChar() {
	charCompleted = false;

	console.log("going to next char");

	setCurStatusMessage(globalConstants.prettyTimeStr[curTestType]);

	clearBackgroundCanvas();
	clearDrawingCanvas();

	strokesList = [];
	atChar += 1;

	if (curTestType == "tutorial") {
		drawHanziSvg(curWords[0].svgdatas[atChar], 0, 0, 0, 1);
		new CanvasDot(correctStrokesThisChar);
	}
}

function doMouseDown(event) {
	updateUserLastInteraction();

	let mousePos = getCanvasMousePos(event);

	// check if mouse is within the canvas

	if (!(mousePos.x > 0 && mousePos.y > 0 && mousePos.x < 480 && mousePos.y < 480)) {
		return;
	}

	if (wordCompleted) {
		goToNextWord();
	}
	else {
		if (curTestType == "draw" || curTestType == "tutorial") {
			if (charCompleted) {
				goToNextChar();
			}
			else {

				// new stroke

				mouseDown = 1;
				strokesList.push([]);
				strokesList[strokesList.length - 1].push(mousePos);

				lastMousePos = mousePos;

				doDraw(event);
			}
		}
		else {
			goToWordEnd();
		}
	}
}

function doMouseMove(event) {
	let mousePos = getCanvasMousePos(event);

	if (mousePos.x > 0 && mousePos.y > 0 && mousePos.x < 480 && mousePos.y < 480) {
		doDraw(event);

		lastMousePos = mousePos;
	}
	else{
		evalStroke();
		mouseDown = 0;
	}
}

function doMouseUp(event) {
	updateUserLastInteraction();

	let mousePos = getCanvasMousePos(event);

	if (mousePos.x > 0 && mousePos.y > 0 && mousePos.x < 480 && mousePos.y < 480) {
		if (strokesList.length > 0) {
			evalStroke();
			mouseDown = 0;
		}
	}
}

function initEventBinds() {

	let preventContextMenus = ["canvas-draw", "proficiencybutton-1", "proficiencybutton-2", "proficiencybutton-3"]

	for (let elemId of preventContextMenus) {
		document.getElementById(elemId).addEventListener("contextmenu", event => event.preventDefault());
	}

	document.getElementById("canvas-draw").onmousedown = function(event) {
		event.preventDefault();
		if (!onTouchScreen && event.button == 0) {
			doMouseDown(event);
		}
	}

	document.body.onmousemove = function(event) {
		if (!onTouchScreen) {
			doMouseMove(event);
		}
	};

	document.getElementById("canvas-draw").onmouseup = function(event) {
		if (!onTouchScreen) {
			doMouseUp(event);
		}
	}

	document.getElementById("canvas-draw").ontouchstart = function(event) {
		onTouchScreen = true;

		doMouseDown(event);
	}

	document.body.ontouchmove = function(event) {
		doMouseMove(event);
	}

	document.getElementById("canvas-draw").ontouchend = function(event) {
		lastMousePos = null; // gets re-set inside draw();

		doMouseUp(event);
	}

	document.body.onkeydown = function(event) {
		if (wordCompleted && (event.key == "1" || event.key == "2" || event.key == "3")) {
			updateUserLastInteraction();

			if (event.key == "1") {
				changeProficiency(1);
			}
			else if (event.key == "2") {
				changeProficiency(2);
			}
			else if (event.key == "3") {
				changeProficiency(3);
			}
		}

		if (event.key == " ") {
			if (wordCompleted) {
				goToNextWord();
				updateUserLastInteraction();
			}
			else if (!wordCompleted && (curTestType == "pronounce" || curTestType == "define")){ // not "Draw"
				goToWordEnd();
				updateUserLastInteraction();
			}
			else if (charCompleted) {
				goToNextChar();
				updateUserLastInteraction();
			}
		}

		if (event.key == " " && event.target === document.body) { // prevent space scrolling
			event.preventDefault();
		}
	};
}
initEventBinds();
