

/*
	Copyright Abhinav Singh Chauhan (@xclkvj)
	Copying the contents of this file by any means is prohibited.
*/

const ViewerBG = '#eee';


const ViewerUI = {
	canvasWrapper: document.getElementById('viewerCanvasWrapper'),
	cubeWrapper: document.getElementById('orientCubeWrapper'),
	togglePan: document.getElementById('togglePan'),
	toggleOrbit: document.getElementById('toggleOrbit'),
	resetBtn: document.getElementById('resetBtn'),
	modelBrowser: document.getElementById('modelBrowser'),
	modelBrowserContent: document.getElementById('modelBrowserContent'),
	fileInput: document.getElementById('fileInput'),
	loader: document.getElementById('loader'),
	loaderInfo: document.getElementById('loaderInfo'),
	webglContainer: document.getElementById('webglContainer'),
};

function setItemSelected(ele, bool) {
	if (bool) {
		ele.classList.add('item-selected');
	} else {
		ele.classList.remove('item-selected');
	}
}

function toggle(ele) {
	if (ele.getBoundingClientRect().height > 0) {
		ele.style.display = 'none';
		return false;
	} else {
		ele.style.display = 'block';
		return true;
	}
}

function toggleThrough(ele, through, cb, selected=true) {
	through.onclick = () => {
		let bool = toggle(ele);
		selected && setItemSelected(through, bool);
		cb && cb(bool);
	}
}

function show(ele) {
	ele.style.display = 'block';
}

function hide(ele) {
	ele.style.display = 'none';
}

function Viewer() {


	

	
	

	let startTime = 0;
	let duration = 500;
	let oldPosition = new THREE.Vector3();
	let newPosition = new THREE.Vector3();
	let play = false;

	

	

	ViewerUI.fileInput.addEventListener('input', function(evt) {
		let file = evt.target.files[0];
		if (file) {
			show(ViewerUI.loader);
			ViewerUI.loaderInfo.innerHTML = 'Reading file...';
			let reader = new FileReader();
			reader.onload = function(e) {
				loadModel(e.target.result);
			}
			reader.onerror = function(err) {
				ViewerUI.loaderInfo.innerHTML = 'Error reading file! See console for more info.';
				console.error(err);
			}
			reader.readAsDataURL(file);
		}
	});
	
	hide(ViewerUI.loader);

	let hasMoved = false;

	function antiMoveOnDown(e) {
		hasMoved = false;
	}
	function antiMoveOnMove(e) {
		hasMoved = true;
	}
	
	window.addEventListener('mousedown', antiMoveOnDown, false);
	window.addEventListener('mousemove', antiMoveOnMove, false);
	window.addEventListener('touchstart', antiMoveOnDown, false);
	window.addEventListener('touchmove', antiMoveOnMove, true);
	
	
	
	

	
	
	
	
	ViewerUI.togglePan.onclick = function() {
		setPanMode();
		setItemSelected(selectedModeElement, false);
		selectedModeElement = this;
		setItemSelected(this, true);
	}
	
	ViewerUI.toggleOrbit.onclick = function() {
		setOrbitMode();
		setItemSelected(selectedModeElement, false);
		selectedModeElement = this;
		setItemSelected(this, true);
	}
	

	
	

   //might be irrelevant. possibly explode related
	function resetAll() {
		controller.reset();
		lineScene.remove.apply(lineScene, lineScene.children);
		spriteScene.remove.apply(spriteScene, spriteScene.children);
		resetSelect();
	}

	function updateSelectDom(child) {
		if (child.itemWrapper) {
			if (child.isSelected) {
				child.itemWrapper.querySelector('.graph-name').style.color = '#03a9f4';
			} else {
				child.itemWrapper.querySelector('.graph-name').style.color = 'inherit';
			}
		}
	}
	
	function setOrbitMode() {
		controller.enableZoom = true;
		controller.enablePan = true;
		controller.enableRotate = true;
		controller.mouseButtons = {
			LEFT: THREE.MOUSE.ROTATE,
			MIDDLE: THREE.MOUSE.DOLLY,
			RIGHT: THREE.MOUSE.PAN
		};
	}
	
	function setPanMode() {
		controller.enableZoom = false;
		controller.enablePan = true;
		controller.enableRotate = false;
		controller.mouseButtons = {
			LEFT: THREE.MOUSE.PAN,
			MIDDLE: THREE.MOUSE.PAN,
			RIGHT: THREE.MOUSE.PAN
		};
	}
	
	
	let wrapper = ViewerUI.canvasWrapper;
	let scene = new THREE.Scene();
	let camera = new THREE.PerspectiveCamera(70, wrapper.offsetWidth / wrapper.offsetHeight, 0.1, 1000);
	
	
	let renderer = new THREE.WebGLRenderer({
		antialias: true,
		alpha: true
	});
	
	renderer.setClearColor( 0x000000 );
	renderer.autoClear = false;
	renderer.setPixelRatio(window.deivicePixelRatio);
	scene.background = null;
	
	const grid = new THREE.GridHelper( 20, 20, 0xc1c1c1, 0x8d8d8d );
				scene.add( grid );

				
	let lineScene = new THREE.Scene();
	let spriteScene = new THREE.Scene();

	function makeCircleImage() {
		let canvas = document.createElement('canvas');
		let ctx = canvas.getContext('2d');
		let size = 32;
		canvas.width = size;
		canvas.height = size;

		let r = size * 0.8 / 2;
		let blur = size - r;
		
		ctx.shadowBlur = 5;
		ctx.shadowColor = '#555';

		ctx.fillStyle = '#fff';
		ctx.beginPath();
		ctx.arc(size / 2, size / 2, r, 0, Math.PI * 2);
		ctx.closePath();
		ctx.fill();

		ctx.shadowBlur = 0;
		ctx.fillStyle = '#009bff';
		ctx.beginPath();
		ctx.arc(size / 2, size / 2, r * 0.5, 0, Math.PI * 2);
		ctx.closePath();
		ctx.fill();

		return canvas;
	}

	let circleTexture = new THREE.CanvasTexture(makeCircleImage())
	let circleMaterial = new THREE.SpriteMaterial({ 
		map: circleTexture,
		sizeAttenuation: false 
	});
	let circleSprite = new THREE.Sprite(circleMaterial);
	circleSprite.scale.setScalar(0.08);

	let lineMaterial = new THREE.LineBasicMaterial({
		color: 0x009bff,
		linewidth: 10
	});

	let activeLine = null;

	
	
	function resetSelect() {
		scene.traverse(child => {
			child.isSelected = false;
			if (child.isMesh && child.material) {	
				updateMeshInteractionMaterial(child);
			}
			updateSelectDom(child);
		});
	}
		

	renderer.domElement.onmousemove = function(evt) {
		evt = evt || window.event;

		
		let x = evt.offsetX;
		let y = evt.offsetY;
		let size = renderer.getSize(new THREE.Vector2());
		let mouse = new THREE.Vector2(x / size.width * 2 - 1, -y / size.height * 2 + 1);
		
		let raycaster = new THREE.Raycaster();
		raycaster.setFromCamera(mouse, camera);

		
		}

	/*renderer.domElement.ontouchmove = function(e) {
		let rect = e.target.getBoundingClientRect();
		let x = e.targetTouches[0].pageX - rect.left;
		let y = e.targetTouches[0].pageY - rect.top;
		renderer.domElement.onmousemove({
			offsetX: x,
			offsetY: y
		});
	}*/

	renderer.domElement.ontouchstart = function(e) {
		let rect = e.target.getBoundingClientRect();
		let x = e.targetTouches[0].pageX - rect.left;
		let y = e.targetTouches[0].pageY - rect.top;
		renderer.domElement.onclick({
			offsetX: x,
			offsetY: y
		});
	}

	
	
	function updateMeshInteractionMaterial(mesh) {
		if (mesh.isHidden) {
			mesh.interactionMaterial.color = hiddenColor;
			mesh.interactionMaterial.opacity = hiddenAlpha;
		} else {
			mesh.interactionMaterial.opacity = 1;
		}
		if (mesh.isSelected) {
			mesh.interactionMaterial.color = selectColor;
			mesh.itemWrapper.querySelector('.graph-name').style.color = '#03a9f4';
		} else {
			mesh.itemWrapper.querySelector('.graph-name').style.color = 'inherit';
		}
		mesh.interactionMaterial.needsUpdate = true;
		if (!mesh.isSelected && !mesh.isHidden) {
			mesh.material = mesh.defaultMaterial;
		} else {
			mesh.material = mesh.interactionMaterial;
		}
	}
	
	function onResize() {
		let width = wrapper.offsetWidth;
		let height = wrapper.offsetHeight;
		renderer.setSize(width, height, false);
		camera.aspect = width / height;
		camera.updateProjectionMatrix();
	}
	
	onResize();
	
	wrapper.appendChild(renderer.domElement);
	window.addEventListener('resize', onResize, false);
	
	let gltfLoader = new THREE.GLTFLoader();
	let loadedScene = null;
	let loadedMeshes = [];
	
	let d = 5;

	let selectColor = new THREE.Color('#42006b');
	let hiddenColor = new THREE.Color('#555');
	let hiddenAlpha = 0.3;

	let interactionMaterial = new THREE.MeshPhongMaterial({
		transparent: true,
		color: selectColor,
		side: THREE.DoubleSide,
		precision: 'mediump'
	});
	
	function loadModel(url) {
		
		resetAll();
		if (loadedScene) {
			scene.remove(loadedScene);
			loadedScene = null;
			loadedMeshes.length = 0;
		}
		
		show(ViewerUI.loader);
		ViewerUI.modelBrowserContent.innerHTML = '';
		ViewerUI.loaderInfo.innerHTML = 'Loading model...';
		
		gltfLoader.load(
			url,
			function onLoad(gltf) {
				
				loadedScene = gltf.scene;
				scene.add(gltf.scene);

				gltf.scene = gltf.scene || gltf.scenes[0];

				let object = gltf.scene;

				const box = new THREE.Box3().setFromObject(object);
				const size = box.getSize(new THREE.Vector3()).length();
				const center = box.getCenter(new THREE.Vector3());

				controller.reset();

				object.position.x += (object.position.x - center.x);
				object.position.y += (object.position.y - center.y);
				object.position.z += (object.position.z - center.z);
				controller.maxDistance = size * 10;
				camera.near = size / 100;
				camera.far = size * 100;
				camera.updateProjectionMatrix();

				camera.position.copy(center);
				camera.position.x += size / 2.0;
				camera.position.y += size + 2.0;
				camera.position.z += size / 2.0;

				directionalLight.position.setScalar(size);

				camera.lookAt(center);

				controller.saveState();

				gltf.scene.traverse((node) => {
					if (node.isMesh && node.material) {
						node.geometry.computeBoundingBox();
						node.material.side = THREE.DoubleSide;
						node.material.precision = 'mediump';
						node.material.needsUpdate = true;
						node.interactionMaterial = interactionMaterial.clone();
						node.defaultMaterial = node.material;
						node.defaultPositionArray = Array.from(node.geometry.attributes.position.array);
						node.defaultPosition = node.position.clone();
						loadedMeshes.push(node);
					}
				});

				let content = ViewerUI.modelBrowserContent;
				let counter = 0;
				let parentLevel = 0;

				function makeSceneGraph(obj) {
					
					if (obj.children.length === 0 && !obj.isMesh) {
						return;
					}
					
					let itemWrapper = document.createElement('div');
					itemWrapper.classList.add('graph-item-wrapper');
					
					let item = document.createElement('div');
					item.classList.add('graph-item');
					
					itemWrapper.appendChild(item);
					
					content.appendChild(itemWrapper);
					let n = 0;
					let obj2 = obj;
					while (obj2 != gltf.scene) {
						obj2 = obj2.parent;
						n++;
					}
					
					item.style.paddingLeft = n * 1.5 + 'em';
					obj.itemWrapper = itemWrapper;
					
					let left = document.createElement('div');
					left.classList.add('graph-left');
					let right = document.createElement('div');
					right.classList.add('graph-right');
					item.appendChild(left);
					item.appendChild(right);
					
					if (obj.children.length > 0) {
						
						parentLevel++;
						let folder = document.createElement('div');
						
						folder.style.marginRight = '10px';
						folder.classList.add('graph-folder');
						folder.innerHTML = '<i class="fa fa-folder-open"></i>';
						left.appendChild(folder);
						
						obj.isFolderOpen = true;
						obj.openFolder = function() {
							folder.innerHTML = obj.isFolderOpen ? '<i class="fa fa-folder-open"></i>' :  '<i class="fa fa-folder"></i>';
							obj.traverse(child => {
								if (obj === child) {
									return;
								}
								if (child.itemWrapper) {
									if (child.parent.isFolderOpen && obj.isFolderOpen) {
										child.itemWrapper.style.display = 'block';
									}
									if (!obj.isFolderOpen) {
										child.itemWrapper.style.display = 'none';
									}
								}
							});
						}
						
						folder.onclick = () => {
							obj.isFolderOpen = !obj.isFolderOpen;
							obj.openFolder();
						}
						
						for (let i = 0; i < obj.children.length; i++) {
							makeSceneGraph(obj.children[i]);
						}
						
					}
					
					let name = document.createElement('div');
					name.classList.add('graph-name');
					name.innerHTML = obj.name || 'None';
					left.appendChild(name);
					
					name.onclick = function() {
						resetSelect();
						obj.traverse(child => {	
							child.isSelected = true;
							if (child.isMesh && child.material) {
								updateMeshInteractionMaterial(child);
							}
							updateSelectDom(child)
						});
					}
					
					let visible = document.createElement('div');
					visible.classList.add('graph-visible');
					visible.innerHTML = '<i class="fa fa-eye"></i>';
					
					obj.showMesh = function() {
						visible.innerHTML = obj.isMeshVisible ? '<i class="fa fa-eye"></i>' : '<i class="fa fa-eye-slash"></i>';
						obj.traverse(child => {
							if (child.itemWrapper) {
								let eye = child.itemWrapper.querySelector('.graph-visible');
								eye.innerHTML = obj.isMeshVisible ? '<i class="fa fa-eye"></i>' : '<i class="fa fa-eye-slash"></i>';
								eye.style.color = obj.isMeshVisible ? 'inherit' : 'rgba(0, 0, 0, 0.3)';
							}
							if (child.isMesh && child.material) {
								child.isHidden = !obj.isMeshVisible;
								updateMeshInteractionMaterial(child);
							}
						});
					}
					
					obj.isHidden = false;
					obj.isSelected = false;
					obj.isMeshVisible = true;
					visible.onclick = function() {
						obj.isMeshVisible = !obj.isMeshVisible;
						obj.showMesh();
					}
					
					right.appendChild(visible)
					
				}
				
				makeSceneGraph(gltf.scene)

				hide(ViewerUI.loader);
				
			},
			function onProgress(xhr) {
				ViewerUI.loaderInfo.innerHTML = Math.round(xhr.loaded / xhr.total * 100) + '% loaded';
			},
			function onError(err) {
				ViewerUI.loaderInfo.innerHTML = 'Error loading model! See console for more info.';
				console.error('Error loading model!', err);
			}
		);
		
	}
	
	
	
	let controller = new THREE.OrbitControls(camera, renderer.domElement);
	controller.enabled = true;
	controller.enableDamping = true;
	controller.dampingFactor = 0.5;
	controller.screenSpacePanning = true;
	
	let selectedModeElement = ViewerUI.toggleOrbit;
	setOrbitMode();

	camera.position.z = d;
	camera.lookAt(scene.position);
	controller.update();
	controller.saveState();
	
	let ambientLight = new THREE.AmbientLight();
	ambientLight.intensity = 1;
	scene.add(ambientLight);

	let directionalLight = new THREE.DirectionalLight();
	directionalLight.position.set(200, 200, 200)
	directionalLight.intensity = 0.5;
	scene.add(directionalLight);
	
	/*let light1 = new THREE.PointLight(0xffffff);
	light1.position.set(100, 100, 100);
	scene.add(light1);
	
	let light2 = new THREE.PointLight(0xffffff);
	light2.position.set(100, 100, -100);
	scene.add(light2);
	
	let light3 = new THREE.PointLight(0xffffff);
	light3.position.set(-100, 100, 100);
	scene.add(light3);
	
	let light4 = new THREE.PointLight(0xffffff);
	light4.position.set(-100, 100, -100);
	scene.add(light4);
	
	light1.intensity = light2.intensity = light3.intensity = light4.intensity = 0.3;*/
	
	let stop = false;

	function renderAll() {

		renderer.clear();
		renderer.render(scene, camera);
		updateCubeCamera();
		renderer.clearDepth();


	}
	
	function animate(time) {

		if (stop) {
			return;
		}

		if (play) {
			let now = Date.now();
			let x = Math.min(1, (now - startTime) / duration);
			camera.position.copy(oldPosition).lerp(newPosition, x)
			if (x === 1) {
				play = false;
			}
		}
		
		requestAnimationFrame(animate);
		controller.update();
		renderAll();
	}
	
	requestAnimationFrame(animate);
	
	return {
		loadModel: loadModel
	};
	
}

function draggable(ele, toggleEle) {
	
	let startX = 0;
	let startY = 0;
	
	function onMouseDown(evt) {
		evt = evt || window.event;
		startDrag(evt.clientX, evt.clientY);
		window.addEventListener('mousemove', onMouseMove, true);
	}
	
	function onMouseMove(evt) {
		evt = evt || window.event;
		let newX = evt.clientX;
		let newY = evt.clientY;
		moveDrag(newX, newY);
	}
	
	function onMouseUp() {
		window.removeEventListener('mousemove', onMouseMove, true);
	}
	
	function startDrag(x, y) {
		startX = x;
		startY = y;
	}
	
	function moveDrag(newX, newY) {
		
		let deltaX = newX - startX;
		let deltaY = newY - startY;
		
		startX = newX;
		startY = newY;

		let x = ele.offsetLeft + deltaX;
		let y = ele.offsetTop + deltaY;
		x < 0 && (x = 0);
		y < 0 && (y = 0);
		let w = ele.parentNode.offsetWidth - ele.offsetWidth;
		let h = ele.parentNode.offsetHeight - ele.offsetHeight;
		x > w && (x = w);
		y > h && (y = h);

		ele.style.left = x + 'px';
		ele.style.top = y + 'px';
		
	}
	
	toggleEle.addEventListener('mousedown', onMouseDown, true);
	window.addEventListener('mouseup', onMouseUp, true);
	
}

