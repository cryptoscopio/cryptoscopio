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

	// Expand/contract record groups when clicked
	for(row of document.querySelectorAll('tr:first-child')){
		row.addEventListener('click', function(e){
			let tbody = e.target.closest('tbody');
			// Prevent groups with selected rows from being closed
			if(!tbody.querySelector('td.selected')){
				tbody.className = tbody.className ? '' : 'closed';
				// Expanding/contracting rows can affect the window bounds and/or
				// the relative position of a row with an active question
				positionSidebar();
			}
		});
	}

	// Positioning logic for the <aside> sidebar with questions about the nature
	// of transfers, which can't be done with pure CSS, unfortunately. If the 
	// contents are taller than the vertical space in <main>, the top becomes
	// sticky when scrolling up, and the bottom becomes sticky when scrolling
	// down. Otherwise, fill and centre within the vertical space.
	function positionSidebar(){
		if(window.activeSidebar){
			let main_rect = document.querySelector('main').getBoundingClientRect();
			let cell_rect = window.activeSidebar.parentNode.getBoundingClientRect();
			let content_rect = window.activeSidebar.querySelector('div.question').getBoundingClientRect();
			// Align top with the top of <main>, unless the contents are large
			// enough to be scrollable and the user has scrolled down
			if(main_rect.top < content_rect.top){
				window.activeSidebar.style.top = (-cell_rect.top + main_rect.top) + 'px';
			}
			// Size to fill the vertical space within <main>, but never smaller
			// than the contents, making it scrollable if needed
			window.activeSidebar.style.height = Math.max(
				main_rect.bottom - main_rect.top,
				content_rect.height
			) + 'px';
		}
	}
	document.querySelector('main').addEventListener('scroll', positionSidebar);
	window.addEventListener('resize', positionSidebar);

	// Handler for selecting options in the sidebar
	function sidebarAction(e){
		e.preventDefault();
		let link = e.target.closest('a');
		// Cancel button handling
		if(link.dataset.action == 'cancel'){
			link.closest('tr').querySelector('td').className = '';
			window.activeSidebar = undefined;
			link.closest('aside').remove();
		// Prevent clicks on the inputs inside the options from triggering
		} else if(!['INPUT', 'SELECT', 'OPTION'].includes(e.target.tagName)){
			// Check if inputs have been correctly filled and show error if not
			if(['price', 'amount'].includes(link.dataset.action) && (
				!link.querySelector('#currency').value ||
				Number.isNaN(Number.parseFloat(link.querySelector('#' + link.dataset.action).value))
			)){
				link.querySelector('#error-message').className = '';
			// Prepare and send request with answer
			} else {
				let record = link.closest('tr').dataset.record;
				
			}
		}
	}

	// Set up listeners for [input required] links in the rightmost column,
	// bringing up a sidebar with questions about the nature of the transfer
	for(input_prompt of document.querySelectorAll('a.input-required')){
		input_prompt.addEventListener('click', function(e){
			e.preventDefault();
			// Use the <template> to initialise a sidebar with the questions
			e.target.parentNode.appendChild(
				document.importNode(
					document.getElementById(e.target.dataset.template).content,
					true
				)
			);
			// Highlight the row that the questions pertain to
			e.target.parentNode.parentNode.querySelector('td').className = 'selected';
			// Re-select so we have an Element reference, not DocumentFragment
			let sidebar = e.target.parentNode.querySelector('aside')
			// Register listeners for selecting the options
			for(link of sidebar.querySelectorAll('a')){
				link.addEventListener('click', sidebarAction);
			}
			// Register the sidebar to be dynamically positioned when the
			// window bounds change, and trigger the positioning
			window.activeSidebar = sidebar;
			positionSidebar();
		});
	}		
});
