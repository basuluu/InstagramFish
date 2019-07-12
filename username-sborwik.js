usernames = []
function jumper(e) {
	console.log(e.keyCode)
	if (e.ctrlKey) {
		switch(e.keyCode) {
			case 90:
				last_name = usernames.pop();
				alert(last_name + ' - удален')
				break;
			case 38:
				username = document.getElementsByClassName('FPmhX notranslate nJAzx')[0].title;
				usernames.push(username);
				document.getElementsByClassName('HBoOv coreSpriteRightPaginationArrow')[0].click();
				break;
			case 40:
				usernames_set = new Set(usernames)
				console.log(usernames_set);
                break;
		}
	}
}

addEventListener("keydown", jumper);



