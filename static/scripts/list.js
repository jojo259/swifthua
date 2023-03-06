"use strict"

let potentialWords = [];
let newPotentials = false;

function saveListDisplayName() {
	fetch("/api/savelistdisplayname", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			listName: flaskData.listName,
			newDisplayName: document.getElementById("listdisplayname").value
		})
	})
	.then((response) => response.json())
	.then((respData) => {
		logApiMessage("savelistdisplayname", respData);
		
		if (!respData.success) {
			createTempNotification(`Error - ${respData.message}`);
			return;
		}

		createTempNotification("Saved display name")
	});
}

function deleteListButton() {
	document.getElementById("actuallydeletelistdiv").removeAttribute("hidden");
}

function saveListTestSettings() {
	fetch("/api/savelistsettings", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			listName: flaskData.listName,
			listDisableTestDraw: document.getElementById("listdisabledraw").checked,
			listDisableTestPronounce: document.getElementById("listdisablepronounce").checked,
			listDisableTestDefine: document.getElementById("listdisabledefine").checked,
		})
	})
	.then((response) => response.json())
	.then((respData) => {
		logApiMessage("savelistsettings", respData);
		
		if (!respData.success) {
			createTempNotification(`Error - ${respData.message}`);
			return;
		}

		createTempNotification("Saved settings")
	});
}

function actuallyDeleteList() {
	console.log("DELETING LIST!");

	fetch("/api/deletelist", {
		method: "DELETE",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json"
		},
		body: JSON.stringify({
			listName: flaskData.listName
		})
	})
	.then((response) => response.json())
	.then((respData) => {
		logApiMessage("deletelist", respData);
		window.location.href = "/lists";
	});
}

function addWordButton(wordToAdd) {
	addWord(wordToAdd, flaskData.listName);
	document.getElementById(`addwordbuttoncontainer-${wordToAdd}`).innerHTML = "Added";
}

function addWordsButton() {
	if (!newPotentials) {
		console.log("can't add words, already sent these");
		return;
	}

	console.log("ADDING WORDS!");

	fetch("/api/listaddwords", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			listName: flaskData.listName,
			wordsToAdd: potentialWords,
		})
	})
	.then((response) => response.json())
	.then((respData) => {
		logApiMessage("listaddwords", respData);
		
		potentialWords.forEach(function(curWord, atWord) {
			if (respData.wordsAdded.includes(curWord)) {
				potentialWords[atWord] += " - added";
			}
			else {
				potentialWords[atWord] += " - not found or already present";
			}
		});

		displayPotentialWords();
		newPotentials = false;
	});
}

function removeWordButton(wordToRemove) {
	console.log("REMOVING WORD!");

	fetch("/api/listremoveword", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			listName: flaskData.listName,
			wordToRemove: wordToRemove,
		})
	})
	.then((response) => response.json())
	.then((respData) => {
		logApiMessage("listremoveword", respData);
		
		let newText = "Error";

		if (respData.success == true) {
			newText = "Removed";
		}

		document.getElementById(`removewordbuttoncontainer-${wordToRemove}`).innerText = newText;
	});
}

function checkAddWordsBox() {
	console.log("checking add words box");

	let curText = document.getElementById("addwordsbox").value;

	potentialWords = [];
	
	let curWord = ""
	for (const curChar of (curText + " ")) {
		if (checkStringIsChinese(curChar)) {
			curWord += curChar;
		}
		else {
			if (curWord.length > 0){
				potentialWords.push(curWord);
				curWord = "";
			}
		}
	}

	document.getElementById("detectedwordsnum").innerText = potentialWords.length;

	displayPotentialWords();
}

function displayPotentialWords() {
	newPotentials = true;

	let detectedWordsElem = document.getElementById("detectedwords");

	let newText = potentialWords.join("\n");
	
	if (detectedWordsElem.innerText != newText) {
		detectedWordsElem.innerText = newText;
		newPotentials = true;
	}
}

function toggleEditOptions() {
	console.log("toggling edit options");

	let divsToToggleHidden = Array.from(document.getElementsByClassName("editoptionstoggled"));

	for(let i = 0; i < divsToToggleHidden.length; i++){
		let curElem = divsToToggleHidden[i];

		if (curElem.hasAttribute("hidden")) {
			divsToToggleHidden[i].removeAttribute("hidden");
		}
		else {
			divsToToggleHidden[i].setAttribute("hidden", "hidden");
		}
	}

	let editListButtonElem = document.getElementById("editlistbutton");

	if (editListButtonElem.innerText == "Edit list") {
		editListButtonElem.innerText = "Stop editing list"
	}
	else {
		editListButtonElem.innerText = "Edit list"
	}
}