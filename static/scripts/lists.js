"use strict"

function doListsSearch() {
	let searchText = document.getElementById("searchtext").value;
	let newUrl = updateQueryString('search', searchText, location.href);
	newUrl = updateQueryString('page', '1', newUrl);
	console.log(newUrl)
	location.href = newUrl;
}

function attemptCreateList() {
	if (flaskData.curUsername == null) {
		createTempNotification("Not logged in, cannot create list");
		return;
	}

	let listName = document.getElementById("listname").value;

	fetch("/api/createlist", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			listName: listName,
		})
	})
	.then((response) => response.json())
	.then((responseData) => {
		logApiMessage("createlist", responseData)

		if (responseData.success != true) {
			createTempNotification(`Error - ${responseData.message}`);
			return;
		}

		window.location.href = "/list/" + responseData.listName;
	});
}

function attemptChooseList(listName) {
	console.log(`choosing list ${listName}`);

	fetch("/api/chooselist", {
		method: "POST",
		headers: {
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			listName: listName,
		})
	})
	.then((response) => response.json())
	.then((responseData) => {
		logApiMessage("chooselist", responseData)

		if (responseData.success != true) {
			createTempNotification(`Error - ${responseData.message}`);
			return;
		}

		createTempNotification(`Successfully set list to ${listName}`);
	});
}