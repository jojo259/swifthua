"use strict"

doExport()

function doExport() {
	let formatStr = document.getElementById("format").value;
	let outputStr = "";
	for (let curWord of flaskData.wordsList) {
		let curWordStr = formatStr;

		curWordStr = curWordStr.replace('[simplified]', curWord._id)
		curWordStr = curWordStr.replace('[traditional]', curWord.traditional)
		curWordStr = curWordStr.replace('[english]', curWord.english)
		curWordStr = curWordStr.replace('[pinyin]', curWord.pinyin)
		curWordStr = curWordStr.replace('[pinyinnumbered]', curWord['pinyin-numbered'])

		outputStr += curWordStr + '\n'
	}

	document.getElementById("output").innerText = outputStr;
}