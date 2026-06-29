
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">

<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />

<script type='text/javascript' src="//cdn2.editmysite.com/js/lang/en/utl.js?buildTime=1782741641&"></script>
<script type='text/javascript' src='https://cdn11.editmysite.com/js/jquery-2.1.4.min.js'></script>
<script type='text/javascript' src='//cdn1.editmysite.com/weebly/libraries/jquery_effects.js?1'></script>
<script type='text/javascript' src='https://cdn11.editmysite.com/js/old/comments-jq.js?buildtime=1782741641' /></script>
<script type='text/javascript' src='https://www.google.com/recaptcha/api.js'/></script>
<script type='text/javascript'>
	var CAPTCHA_REQUIRED = true;

	//If the blog comment view is not being loaded in an iframe, always show captcha
	if (window.self === window.top) CAPTCHA_REQUIRED = true;
</script>
<style>
body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
.grecaptcha-badge { display: none !important }
</style>
<link rel='stylesheet' href='https://cdn11.editmysite.com/css/old/common-v2.css?buildtime=1782741641' type='text/css' />
			<link rel='stylesheet' href='//www.friendsofhollinhills.org/files/main_style.css' type='text/css' />
	</head>
<body style='margin: 0; padding: 0 0 0 4px; background: transparent !important; text-align: left' class='wsite-theme-light'>

		<div id='commentPostDiv' >
			<form id='commentPostArea' action='/editor/apps/postComment.php' method='post' onsubmit='submitComment(); return;'>
				<div id='commentInputs'>
					<div class='field'>
						<label for='commentName'>
							<span class='label'>Name</span>
							<span class='required'>(required)</span>
						</label>
						<div class='commentInput'><input type='text' name='name' id='commentName' /></div>
					</div>

					
			<div class="field">
				<label for="commentEmail">
					<span class="label">Email</span>
					<span class="notice">(not published)</span>
				</label>
				<div class="commentInput">
					<input type="text" name="email" id="commentEmail" value="" />
				</div>
			</div>
		

					
			<div class="field">
				<label for="commentWebsite">
					<span class="label">Website</span>
				</label>
				<div class="commentInput"><input type="text" name="website" id="commentWebsite" /></div>
			</div>
		

					<div class='field'>
						<label for='commentComment'>
							<span class='label'>Comments</span>
							<span class='required'>(required)</span>
						</label>
						<div class='commentTextarea'><textarea name='comment' id='commentComment' rows='10' cols='40'></textarea></div>
					</div>

					<div class='field field-checkbox field-notify'>
						<label for='commentNotify'>
							<input type='checkbox' name='notify' id='commentNotify' />
							<span>Notify me of new comments to this post by email</span>
						</label>
					</div>
				</div>

				<div id='g-recaptcha' data-size='invisible' data-sitekey='6Ldf5h8UAAAAAJFJhN6x2OfZqBvANPQcnPa8eb1C'></div>

				<input type='hidden' id='commentPostId' name='postid' value='546694800602228024' />
				<input type='hidden' id='blogId' name='blogId' value='116148321790435193' />
				<input type='hidden' id='userId' name='userId' value='121874536' />
				<input type='hidden' id='parentId' name='parentId' value='' />
				<input type='hidden' id='parentURL' name='parentURL' value='www.friendsofhollinhills.org' />
		 <span id='commentSubmit' class='blog-button' onclick='document.getElementById("commentPostArea").onsubmit();'><span>Submit</span></span><div class="clear" style="clear: both;"></div></form><div id='errorMessage'></div></div></div>