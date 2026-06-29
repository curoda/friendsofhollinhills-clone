	<!DOCTYPE html>
	<html>

	<head>
		<title>Google Maps Output</title>
		<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
		<meta charset="utf-8">
		<style>
			html,
			body,
			#mapContainer {
				margin: 0;
				padding: 0;
				height: 100%;
			}

			#mapContainer {
				width: 100%;
				text-align: center;
			}

			a {
				color: #06C;
				text-decoration: none;
			}

			a:visited {
				color: #06C;
			}

			.gm-style .gm-style-iw-c {
				border-radius: 0 !important;
			}

			.gm-style-iw {
				text-align: left;
			}

			.leaflet-popup-content-wrapper-left {
				width: 50%;
				display: inline-block;
			}

			.leaflet-popup-content-wrapper-left a {
				text-decoration: underline;
				color: #333;
			}

			.leaflet-popup-content-wrapper-right {
				width: 50%;
				text-align: right;
				display: inline-block;
				vertical-align: top;
			}

			.leaflet-popup-content-wrapper-right a {
				text-decoration: underline;
				color: #333;
			}

			.leaflet-popup-content-wrapper-right button {
				border: none;
				background: none;
				text-decoration: underline;
				color: #333;
				cursor: pointer;
			}
		</style>
		<script type="text/javascript" src="https://maps.googleapis.com/maps/api/js?v=3&client=gme-weeblyinc1"></script>
		<script type="text/javascript">
			//<![CDATA[
			const primaryColor = '000';
			const primaryContrastColor = 'FFF';

			// send a cross domain iframe mesage to the parent to resize the frame to this height
			var resizeMessage = function(event) {
				var imageHeight = document.getElementById('mapContainer').clientHeight;

				window.parent.postMessage(
					imageHeight,
					'*'
				);
			};

			function setMarkerIcon(point, svg) {
				point.setIcon({
					url: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg),
				});
			}

			function createMarkerSvg(isFilled = true) {
				const pinColor = isFilled ? primaryColor : primaryContrastColor;
				const pinBorderColor = primaryColor;
				const pinCircleColor = primaryContrastColor;
				const pinCircleBorderColor = isFilled ? primaryContrastColor : primaryColor;
				return '<svg width="24" height="34" viewBox="0 0 24 34" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M23 11.9403C23 13.3823 22.4408 15.3712 21.4847 17.6402C20.54 19.8822 19.2523 22.2959 17.8934 24.5521C16.5353 26.8069 15.118 28.8845 13.9233 30.4526C13.3252 31.2377 12.7912 31.8842 12.3547 32.3576C12.2246 32.4987 12.1062 32.6211 12 32.7251C11.8938 32.6211 11.7754 32.4987 11.6453 32.3576C11.2088 31.8842 10.6748 31.2377 10.0767 30.4526C8.88205 28.8845 7.46474 26.8069 6.10661 24.5521C4.74766 22.2959 3.45995 19.8822 2.51528 17.6402C1.5592 15.3712 1 13.3823 1 11.9403C1 5.90283 5.92016 1 12 1C18.0798 1 23 5.90283 23 11.9403Z" fill="#' + pinColor + '" stroke="#' + pinBorderColor + '" stroke-width="2"/><circle cx="12" cy="12" r="6" fill="#' + pinCircleColor + '" stroke="#' + pinCircleBorderColor + '" stroke-width="2"/></svg>';
			}

			function clickViewMoreLink(id) {
				if (id) {
					var url = (window.location != window.parent.location) ?
						document.referrer :
						document.location.href;

					var postData = {
						view_more_info_click: id
					}
					window.parent.postMessage(JSON.stringify(postData), url);
				}
			}

			function gLoad() {
				var touchSupported = (('ontouchstart' in window) || window.DocumentTouch && document instanceof DocumentTouch),
					forceTouch = false;

				var forceMapDrag = false;
				var useGestures = false;

				var myLatLng = new google.maps.LatLng(0, 0);
				var locations = null;
				var mapOptions = {
					scrollwheel: false,
					center: myLatLng,
					zoom: 0,
					panControl: false, zoomControl: false,
					scaleControl: false,
					mapTypeControl: false,
					streetViewControl: false,
					mapTypeId: google.maps.MapTypeId.ROADMAP,
					draggable: false				};

				if ((touchSupported || forceTouch) && !forceMapDrag) {
					mapOptions.draggable = false;
					mapOptions.panControl = false;
					mapOptions.scrollwheel = false;
					mapOptions.zoomControlOptions = {
						style: google.maps.ZoomControlStyle.SMALL
					};
					mapOptions.zoomControl = false;
				}

				if (useGestures) {
					mapOptions.gestureHandling = 'greedy';
					mapOptions.panControl = true;
					mapOptions.scrollwheel = true;
				}

				// Use pre-v3.22 controls until the element can be updated with options for the new controls
				google.maps.controlStyle = 'azteca';

				function renderMap(options) {
					var map = new google.maps.Map(document.getElementById("map"), options);
					var activeMarker;
					var hoverMarkerIndex;
					var hasMapPoint = false;
					var hasInfoWindow = true;
					var activeMarkerId = null;

					// reset zoom level to display all markers
					var bounds = new google.maps.LatLngBounds();

					// marker designs
					const filledMarker = createMarkerSvg(true);
					const strokedMarker = createMarkerSvg(false);

					var markers = [];
					var infowindow = null;
					if (hasInfoWindow) {
						infowindow = new google.maps.InfoWindow();
					}

					var isMarkerFixedInCenter = false;

					if (hasMapPoint) {
						var point = new google.maps.Marker({
							position: myLatLng,
							map: map,
							optimized: false
						});
						setMarkerIcon(point, filledMarker);
					}

					function removeAllMarkers() {
						for (const marker of markers) {
							marker.setMap(null);
						}

						markers = [];
					}

					function escapeHtml(str) {
						if (str === null || str === undefined) return '';
						return String(str)
							.replace(/&/g, '&amp;')
							.replace(/</g, '&lt;')
							.replace(/>/g, '&gt;')
							.replace(/"/g, '&quot;')
							.replace(/'/g, '&#39;');
					}

					function renderLocationToMarker(shop, height) {
						if (shop.lat && shop.long) {
							const marker = new google.maps.Marker({
								id: shop.id,
								position: new google.maps.LatLng(shop.lat, shop.long),
								map: map,
								animation: 4,
								optimized: false,
								zIndex: height
							});

							bounds.extend(marker.position);
							setMarkerIcon(marker, strokedMarker);

							google.maps.event.addListener(marker, 'click', (function(marker, i) {
								return function() {
									if (infowindow) {
										var infowindowContent =
											'<div class="leaflet-popup-content-wrapper-left">' +
											'<h3 class="firstHeading">' + escapeHtml(shop.display_name) + '</h3>' +
											'<div id="bodyContent">' +
											'<p>' + escapeHtml(shop.address) + '</p>';

										if (shop.phone) {
											infowindowContent += '<p><a href="tel:' + escapeHtml(shop.phone) + '">' + escapeHtml(shop.phone) + '</a></p>';
										}

										infowindowContent +=
											'</div></div>' +
											'<div class="leaflet-popup-content-wrapper-right"><p><button class="view-more-btn" data-marker-id="' + escapeHtml(String(marker.id)) + '">View more info</button></p>' +
											'</div>';

										infowindow.setContent(infowindowContent);
										infowindow.open(map, marker);

										google.maps.event.addListener(infowindow, 'domready', function() {
											var btn = document.querySelector('.view-more-btn[data-marker-id="' + escapeHtml(String(marker.id)) + '"]');
											if (btn) {
												btn.addEventListener('click', function() {
													clickViewMoreLink(marker.id);
												});
											}
										});
									}

									// check to see if activeMarker is set
									// if so, set the icon back to the default
									activeMarker && activeMarker.setIcon({
										url: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(strokedMarker),
									});

									activeMarker && activeMarker.setZIndex(i);

									// set the icon for the clicked marker
									marker.setIcon({
										url: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(filledMarker),
									});

									// clicked marker on top
									marker.setZIndex(height + 999);

									// update the value of activeMarker
									activeMarker = marker;

									// relay message of location id to website
									var url = (window.location != window.parent.location) ?
										document.referrer :
										document.location.href;

									var postData = {
										location_click_event: marker.id
									}

									window.parent.postMessage(JSON.stringify(postData), url);
								};
							})(marker, height));

							markers.push(marker);

							// Add hover state to marker
							marker.addListener('mouseover', function() {
								marker.setIcon({
									url: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(filledMarker),
								});
								marker.setZIndex(height + 1000);
							});

							// remove hover state if marker is not currently active
							marker.addListener('mouseout', function() {
								if (marker !== activeMarker) {
									marker.setIcon({
										url: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(strokedMarker),
									});
									marker.setZIndex(height);
								}
							});
						}
					}

					if (locations) {
						locations.forEach(renderLocationToMarker);

						//now fit the map to the newly inclusive bounds
						map.fitBounds(bounds);
					}

					
					if (activeMarkerId) {
						var index = markers.findIndex(x => x.id == activeMarkerId);
						google.maps.event.trigger(markers[index], 'click');
						activeMarkerId = null;
					}

					// Maps loaded hidden (like in an accordion) don't center property as their width is often detected as 0.
					// Detect when the iFrame "resizes" and reset the center
					google.maps.event.addDomListener(window, 'resize', function() {
						google.maps.event.trigger(map, 'resize');
						map.setCenter(myLatLng);
						if (locations) {
							map.fitBounds(bounds);
						}
					});

					var SET_TIMEOUT_MS = 200;

					if (isMarkerFixedInCenter) {
						google.maps.event.addListener(map, 'center_changed', function() {
							// 0.2 seconds after the center of the map has changed,
							// set back the marker position.
							window.setTimeout(function() {
								var center = map.getCenter();
								point.setPosition(center);
							}, SET_TIMEOUT_MS);
						});

						google.maps.event.addListener(map, 'dragend', function(evt) {
							// Wait for the center to be changed before saving the Lat/Lng
							window.setTimeout(function() {
								var url = (window.location != window.parent.location) ?
									document.referrer :
									document.location.href;
								var center = map.getCenter();
								var postData = {
									lat: center.lat(),
									lng: center.lng(),
									message: 'marker_position_update_'
								}
								window.parent.postMessage(JSON.stringify(postData), url);
							}, SET_TIMEOUT_MS + 25);

						});
					}

					map.addListener('click', function() {
						var url = (window.location != window.parent.location) ?
							document.referrer :
							document.location.href;
						window.parent.postMessage('map_click_event_', url);
					});

					window.addEventListener('message', ({
						data = {},
						origin
					}) => {
						var allowedOriginPattern = /^https?:\/\/(([\w-]+\.)*beta\.weebly\.com|([\w-]+\.)*weebly\.net|www\.weebly\.com|www1\.weebly\.com|www\.editmysite\.com)$/;
						if (!allowedOriginPattern.test(origin)) {
							return;
						}
						switch (data.event) {
							case 'replace:locations': {
								removeAllMarkers();

								locations = JSON.parse(data.data);
								locations.forEach(renderLocationToMarker);
							}
							break;

							case 'open:location':
							case 'hover:location': {
								if (data.event && data.data && locations) {
									var eventType = data.event;
									var activeLocationId = data.data;
									var index = markers.findIndex(x => x.id == activeLocationId);

									if (eventType === 'open:location') {
										google.maps.event.trigger(markers[index], 'click');
										map.fitBounds(bounds);
									}

									if (eventType === 'hover:location') {
										if (hoverMarkerIndex) {
											google.maps.event.trigger(markers[hoverMarkerIndex], 'mouseout');
										}
										google.maps.event.trigger(markers[index], 'mouseover');
										hoverMarkerIndex = index;
										map.fitBounds(bounds);
									}
								}
							}
							break;
						}

					});
				};

				var mapZoomScale = 0;
				if (mapZoomScale > 0) {
					var maxZoomService = new google.maps.MaxZoomService();
					maxZoomService.getMaxZoomAtLatLng({
						lat: parseFloat(0),
						lng: parseFloat(0),
					}, function(response) {
						const success = response.status === 'OK';
						var maxZoomLevel = success ? response.zoom : 18;
						var zoomLevel = Math.round(maxZoomLevel * (mapZoomScale / 100));
						zoomLevel = zoomLevel < 1 ? mapOptions.zoom : zoomLevel;
						mapOptions.zoom = zoomLevel;
						renderMap(mapOptions);
					});
				} else {
					renderMap(mapOptions);
				}
			}

			//]]>
		</script>

	</head>

	<body onload="gLoad();" style="margin: 0; padding: 0;">

		<div id="mapContainer">
			<div id="map" style="height: 250px; max-width: 100%; margin: 0 auto;"></div>
		</div>

	</body>

	</html>
