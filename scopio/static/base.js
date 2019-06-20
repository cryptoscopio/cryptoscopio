window.addEventListener('load', function(event){
	// Register open dialogue triggers for clicking on header menu items
	for(menu_item of document.querySelectorAll('header menu li')){
		menu_item.addEventListener('click', function(e){
			document.getElementById(e.target.dataset.target).className = 'open';
		});
	}
	// Open a dialogue that's pending to be opened, if any. Invoked after closing dialogues.
	function openPending(){
		let pending = document.querySelector('dialog.pending');
		if(pending){
			pending.className = 'open';
		}
	}
	// Register close dialogue triggers for clicking the dialogue's cancel button
	for(cancel_button of document.querySelectorAll('dialog input[type="button"]')){
		cancel_button.addEventListener('click', function(e){
			e.target.closest('dialog').className = '';
			openPending();
		});
	}
	// Register close dialogue triggers for clicking within the dialogue backdrop
	for(dialogue of document.querySelectorAll('dialog')){
		dialogue.addEventListener('click', function(e){
			if(e.target.tagName == 'DIALOG'){
				e.target.className = '';
				openPending();
			}
		});
	}
	// Register close dialogue trigger when Escape key is pressed
	document.addEventListener('keyup', function(e){
		if(e.key == 'Escape' || e.key == 'Esc'){
			for(open_dialogue of document.querySelectorAll('dialog.open')){
				open_dialogue.className = '';
			}
			openPending();
		}
	});
	// Open a dialogue if a matching id is in the current URL hash
	let url = new URL(window.location);
	if(url.hash){
		let dialog = document.querySelector(url.hash);
		if(dialog && dialog.tagName == 'DIALOG'){
			dialog.className = 'open';
		}
	}

	for(row of document.querySelectorAll('tr:first-child')){
		row.addEventListener('click', function(e){
			let tbody = e.target.closest('tbody');
			tbody.className = tbody.className ? '' : 'closed';
		});
	}
});
