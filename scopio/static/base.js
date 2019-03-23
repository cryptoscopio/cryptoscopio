window.addEventListener('load', function(event) {
	const upload_select = document.getElementById('upload-select');
	const upload_input = document.getElementById('upload-input');
	// Upload the selected files
	upload_input.addEventListener('change', function(e){
		upload_select.setAttribute('disabled', true);
		const default_option = upload_select.getElementsByClassName('default-option')[0];
		function resetDropdown() {
			upload_select.removeAttribute('disabled');
			default_option.innerText = 'Upload records...';
		}
		function showError(error_message) {
			// Reset the dropdown and show error (TODO: show error in DOM)
			resetDropdown();
			console.log(error_message);
		}
		const upload_request = new XMLHttpRequest();
		const upload_data = new FormData();
		// Display upload progress as the selected option
		default_option.innerText = 'Uploading... 0%';
		upload_request.upload.addEventListener('progress', function(upload_event){
			if(upload_event.lengthComputable) {
				const percentage = Math.round(upload_event.loaded / upload_event.total * 100);
				// Not an ideal way of detecting completion, but listening for "loadend"
				// on the upload object doesn't work as expected
				if(percentage == 100)
					default_option.innerText = 'Processing...';
				else
					default_option.innerText = 'Uploading... ' + percentage + '%';
			}
		});
		upload_request.addEventListener('abort', function(upload_event){
			showError('The upload was aborted');
		});
		upload_request.addEventListener('timeout', function(upload_event){
			showError('The upload timed out');
		});
		upload_request.addEventListener('error', function(upload_event){
			showError('The upload encountered an error');
		});
		upload_request.addEventListener('loadend', function(upload_event){
			resetDropdown();
		});
		upload_request.open('POST', '.?record_type=' + upload_input.recordType, true)
		// Get CSRF cookie
		const csrf_token = document.cookie.replace(/(?:(?:^|.*;\s*)csrftoken\s*\=\s*([^;]*).*$)|^.*$/, "$1");
		upload_request.setRequestHeader('X-CSRFToken', csrf_token);
		for (let i=0; i<this.files.length; i++) {
			upload_data.append('records', this.files[i]);
		}
		
		upload_request.send(upload_data);
	});
	// The listener must be on click for opening the file browse dialogue to be allowed
	upload_select.addEventListener('click', function(e){
		if(e.target.value) {
			upload_input.recordType = e.target.value;
			upload_input.click();
		}
	});
	// Reset the select right away, though this breaks accessibility (TODO: rethink this)
	upload_select.addEventListener('change', function(e){
		e.target.selectedIndex = 0;
	});
	// Enable the upload selection once we're ready to handle it
	upload_select.removeAttribute('disabled');
});
