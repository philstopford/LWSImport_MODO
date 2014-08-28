#python
import math
import string
import os
import lx

script_name = "Limited LWS Import"
script_ver = "0.0.6"

'''
	0.0.6 (2014/08/26) :
		Adding some comments to the code.
		LWID preflight detection:
			Expectation is that script is used to import LWS into a clean scene, but users will be users.
			 Need to handle case where we find LWIDs on scene items before we start. Options :
			  (Remove those LWID tags to avoid misfires (preferably in pre-flight).)
			  -> Prefix LWID tags to avoid flagging them.
			  (Additional tag to indicate that this item has already been processed before and can be ignored.)

	0.0.5 (2014/08/26) :
		Attempt to be more intelligent about out-of-content folder handling.
			Try and check for existing files in matched replacement folder(s) for a particular inaccessible path.

	0.0.4 (2014/08/23) :
		Hierarchy code working.
		Working on better path handling for objects outside content folder.
		Failsafe importLWO to create an empty mesh if the import for any object fails.

	0.0.3 (2014/08/23) :
		Initial QA and validation before next push.
		Basic camera support.
		Initial stab at hierarchy code.

	0.0.2 (2014/08/22) :
		Simplified key creation using helper.
		LWID tagging implemented to simplify post-process (parenting/targeting)
		Initial LWO implementation.
			Draft layered LWO support. Note that discontinuous layer usage is not supported.
		Initial scope for null handling.

	0.0.1 (2014/08/22) :
		File request for scene selection
		Basic scene setup (start, end frame, frame rate)
		Light extraction (name, type, position/rotation/scale keyframes (no slopes))
		Initial planning for hierarchy reconstruction using item/parent item IDs from LW.
		Initial planning for targeting

	Note about LW item IDs :
		These are used for reconstructing hierarchies in a yet-to-be-implemented post-process pass.
		LW uses a genus integer prefix to its item IDs that we can use in this process to optimize searches.
'''

contentDir_LW = ""
content = []
lights = []
objects = []
cameras = []
meshList = []
locatorList = []
meshLocatorList = []
lightList = []
cameraList = []
parentSearchList = []
originalPathList = []
replacementPathList = []

# Basic light class
class Light:
	numberOfLights = 0
	def __init__(self, name, lwitemid, parentlwitemid, targetlwitemid, color, lightType,
				xposkeys, xposvals, yposkeys, yposvals, zposkeys, zposvals,
				hrotkeys, hrotvals, protkeys, protvals, brotkeys, brotvals,
				xsclkeys, xsclvals, ysclkeys, ysclvals, zsclkeys, zsclvals):
		self.name = name
		self.lwitemid = lwitemid
		self.modoid = 'undefined' # will be set in later stage.
		self.parentlwitemid = parentlwitemid # 0 if there is no parent.
		self.targetlwitemid = targetlwitemid # 0 if there is no target.
		self.color = color
		self.type = lightType
		self.xposkey = xposkeys
		self.xposval = xposvals
		self.yposkey = yposkeys
		self.yposval = yposvals
		self.zposkey = zposkeys
		self.zposval = zposvals
		self.hrotkey = hrotkeys
		self.hrotval = hrotvals
		self.protkey = protkeys
		self.protval = protvals
		self.brotkey = brotkeys
		self.brotval = brotvals
		self.xsclkey = xsclkeys
		self.xsclval = xsclvals
		self.ysclkey = ysclkeys
		self.ysclval = ysclvals
		self.zsclkey = zsclkeys
		self.zsclval = zsclvals

		Light.numberOfLights += 1

# Basic object class
class Object:
	numberOfObjects = 0
	def __init__(self, lwofile, lwolayer, lwitemid, isnull, parentlwitemid, targetlwitemid,
				xposkeys, xposvals, yposkeys, yposvals, zposkeys, zposvals,
				hrotkeys, hrotvals, protkeys, protvals, brotkeys, brotvals,
				xsclkeys, xsclvals, ysclkeys, ysclvals, zsclkeys, zsclvals):
		self.lwofile = lwofile # name if null
		self.lwolayer = lwolayer # 0 if null
		self.lwitemid = lwitemid
		self.isnull = isnull # boolean
		self.modoid = 'undefined' # will be set in later stage.
		self.parentlwitemid = parentlwitemid # 0 if there is no parent.
		self.targetlwitemid = targetlwitemid # 0 if there is no target.
		self.xposkey = xposkeys
		self.xposval = xposvals
		self.yposkey = yposkeys
		self.yposval = yposvals
		self.zposkey = zposkeys
		self.zposval = zposvals
		self.hrotkey = hrotkeys
		self.hrotval = hrotvals
		self.protkey = protkeys
		self.protval = protvals
		self.brotkey = brotkeys
		self.brotval = brotvals
		self.xsclkey = xsclkeys
		self.xsclval = xsclvals
		self.ysclkey = ysclkeys
		self.ysclval = ysclvals
		self.zsclkey = zsclkeys
		self.zsclval = zsclvals

		Object.numberOfObjects += 1

# Basic camera class
class Camera:
	numberOfCameras = 0
	def __init__(self, name, lwitemid, parentlwitemid, targetlwitemid,
				xposkeys, xposvals, yposkeys, yposvals, zposkeys, zposvals,
				hrotkeys, hrotvals, protkeys, protvals, brotkeys, brotvals):
		self.name = name
		self.lwitemid = lwitemid
		self.modoid = 'undefined' # will be set in later stage.
		self.parentlwitemid = parentlwitemid # 0 if there is no parent.
		self.targetlwitemid = targetlwitemid # 0 if there is no target.
		self.xposkey = xposkeys
		self.xposval = xposvals
		self.yposkey = yposkeys
		self.yposval = yposvals
		self.zposkey = zposkeys
		self.zposval = zposvals
		self.hrotkey = hrotkeys
		self.hrotval = hrotvals
		self.protkey = protkeys
		self.protval = protvals
		self.brotkey = brotkeys
		self.brotval = brotvals

		Camera.numberOfCameras += 1

# Ask for LW scene
def main():
	global contentDir_LW
	lx.out("{%s %s} started" % (script_name, script_ver))
	contentDir_LW = lx.eval('pref.value lwio.lwoContentDir ?')
	lwsFile = customfile('fileOpen', 'Load LWS file', 'lws', 'LWS', '*.lws', contentDir_LW)
	if (lwsFile != None):
		preflightChecks()
		parser_main(lwsFile)
	else:
		sys.exit()

# Preflight checks to avoid misfires from previous runs, etc.
def preflightChecks():
	# We need to check the scene items for LWID tags and tweak them to avoid using them in the hierarchy, etc. steps later.
	# We will prefix any numerical values with 'x' to disable them. We will have a penalty in runtime as we will still hoover them up.
	lx.out("Running preflight checks for LWID tags...")
	for i in range(lx.eval('query sceneservice item.N ?')):
		itemID = lx.eval('query sceneservice item.id ? %s' % i)
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % itemID)
		item_name = lx.eval('item.name ?')
		item_tags, item_tagValues = buildHierarchy_itemTags(item_name)
		if (len(item_tags) != 0):
			lx.out("item tags found. Searching....")
			try :
				lwidIndex = item_tags.index('LWID')
			except:
				break
			lx.out('LWID tag found at : {%d} ' % lwidIndex)
			lwidValue = item_tagValues[lwidIndex]
			lx.out('LWID value : {%s} ' % lwidValue)
			#Add our prefix
			if (lwidValue.startswith('x')):
				pass
			else:
				lx.eval('!item.tag string LWID x%s' % lwidValue)

# Read the scene file into memory and drive the scene set up in modo
def parser_main(fname):
	global content
	#Load our scene into a list
	with open(fname) as f:
		content = f.read().splitlines()
	lineCounter = 0
	if (content[lineCounter] != 'LWSC'):
		reportError('Could not detect LWS marker in file. Aborting')

	sceneProperties()
	doLights()
	doObjects()
	doCameras()
	buildHierarchy()

# Three coordinating methods to handle the lights, cameras and geo import.
def doLights():
	parseLights()
	makeLights()

def doObjects():
	parseObjects()
	makeObjects()

def doCameras():
	parseCameras()
	makeCameras()

# Read out light properties and set properties in class
def parseLights():
	global content
	global lights
	# Determine number of lights to process and corresponding lines
	lightLines = []
	lights = []
	lineCounter = 0
	light_targetitemID_LW = "0"
	light_parentitemID_LW = "0"
	lightIndex = -1 # sets to 0 with first light added :)
	for lineCounter in range(len(content)):
		if(content[lineCounter].startswith('AddLight')):
			lightLines.append(lineCounter)
	lx.out('Found %d lights to create' % len(lightLines))

	# So now we need to work with the fixed light structure. Only native lights are supported in this parser.
	for lightNumber in range(len(lightLines)):
		startLine = lightLines[lightNumber]
		if (lightNumber != (len(lightLines) - 1)):
			endLine = lightLines[lightNumber + 1]
		else:
			for lineCounter in range(startLine, len(content)):
				if (content[lineCounter].startswith('AddCamera')): # End of last light block.
					endLine = lineCounter

		# We need our ID here to handle parenting later.
		light_itemID_LW = extractValue(content[startLine])
		lightName = extractValue(content[startLine + 1])

		light_parentitemID_LW = 0
		# Basic color; we pick up any target and parent item IDs in the process as well - they appear before the light color definition
		for lineCounter in range(startLine, endLine):
			if(content[lineCounter].startswith('ParentItem')):
				tempString = content[lineCounter].split(' ')
				light_parentitemID_LW = tempString[1]
			if(content[lineCounter].startswith('TargetItem')):
				tempString = content[lineCounter].split(' ')
				light_targetitemID_LW = tempString[1]
			if(content[lineCounter].startswith('LightColor')):
				lightColorLine = lineCounter
				break
		lightColor = extractValue(content[lightColorLine])

		xpos_start, xpos_end = keyBlockExtract('xpos',startLine, endLine)
		xpos_keys = []
		xpos_vals = []
		animationExtract(xpos_start, xpos_end, xpos_keys, xpos_vals)

		ypos_start, ypos_end = keyBlockExtract('ypos',startLine, endLine)
		ypos_keys = []
		ypos_vals = []
		animationExtract(ypos_start, ypos_end, ypos_keys, ypos_vals)

		zpos_start, zpos_end = keyBlockExtract('zpos',startLine, endLine)
		zpos_keys = []
		zpos_vals = []
		animationExtract(zpos_start, zpos_end, zpos_keys, zpos_vals)

		hrot_start, hrot_end = keyBlockExtract('hrot',startLine, endLine)
		hrot_keys = []
		hrot_vals = []
		animationExtract(hrot_start, hrot_end, hrot_keys, hrot_vals)

		prot_start, prot_end = keyBlockExtract('prot',startLine, endLine)
		prot_keys = []
		prot_vals = []
		animationExtract(prot_start, prot_end, prot_keys, prot_vals)

		brot_start, brot_end = keyBlockExtract('brot',startLine, endLine)
		brot_keys = []
		brot_vals = []
		animationExtract(brot_start, brot_end, brot_keys, brot_vals)

		xscl_start, xscl_end = keyBlockExtract('xscl',startLine, endLine)
		xscl_keys = []
		xscl_vals = []
		animationExtract(xscl_start, xscl_end, xscl_keys, xscl_vals)

		yscl_start, yscl_end = keyBlockExtract('yscl',startLine, endLine)
		yscl_keys = []
		yscl_vals = []
		animationExtract(yscl_start, yscl_end, yscl_keys, yscl_vals)

		zscl_start, zscl_end = keyBlockExtract('zscl',startLine, endLine)
		zscl_keys = []
		zscl_vals = []
		animationExtract(zscl_start, zscl_end, zscl_keys, zscl_vals)

		# Establish light type
		for lineCounter in range(startLine, endLine):
			if(content[lineCounter].startswith('Plugin LightHandler')):
				tempArray = content[lineCounter].split(' ')
				lightType_LW = tempArray[len(tempArray)-1]
				# These are aligned with the lightTypes dictionary in the makeLights() method.
				lightType = 0 # default
				if(lightType_LW == 'DistantLight'):
					lightType = 0
				if(lightType_LW == 'AreaLight'):
					lightType = 1
				if(lightType_LW == 'LinearLight'):
					lightType = 2
				if(lightType_LW == 'DomeLight'):
					lightType = 3
				if(lightType_LW == 'PointLight'):
					lightType = 5
				if(lightType_LW == 'SpotLight'):
					lightType = 7
				# Quit our loop - we found the light handler, and there's only one per light.
				break

		# Create a new light instance in our list.
		lights.append(Light(lightName, light_itemID_LW, light_parentitemID_LW, light_targetitemID_LW, lightColor, lightType,
							xpos_keys, xpos_vals, ypos_keys, ypos_vals, zpos_keys, zpos_vals,
							hrot_keys, hrot_vals, prot_keys, prot_vals, brot_keys, brot_vals,
							xscl_keys, xscl_vals, yscl_keys, yscl_vals, zscl_keys, zscl_vals
							))

# Make our lights and set them up to match LW configuration based on light class
def makeLights():
	global lights
	lightTypes = {0:'sunLight', 1:'areaLight', 2:'cylinderLight', 3:'domeLight', 4:'photometryLight', 5:'pointLight', 6:'portal', 7:'spotLight'}
	for light in lights:
		lx.eval('!item.create %s' % lightTypes[light.type])
		lx.eval('!item.name {%s} %s' % (light.name, lightTypes[light.type]))

		# Add our LW ID for targeting/parenting later.
		lx.eval('!item.tag string LWID %s' % light.lwitemid)

		lightName = lx.eval('query sceneservice selection ? light')
		light.modoid = lightName

		# Transform items
		lx.eval('transform.add pos')
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % lightName)
		lx.eval('transform.add rot')
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % lightName)
		lx.eval('transform.add scl')
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % lightName)
		pos_xfrm_item = lx.eval('query sceneservice item.xfrmPos ? {%s}' % lightName)
		rot_xfrm_item = lx.eval('query sceneservice item.xfrmRot ? {%s}' % lightName)
		scl_xfrm_item = lx.eval('query sceneservice item.xfrmScl ? {%s}' % lightName)

		# Position keys
		lx.eval('select.channel {%s:pos.X} set' % pos_xfrm_item)
		for key in range(len(light.xposkey)):
			makeKey(light.xposkey[key], light.xposval[key])
		lx.eval('select.channel {%s:pos.Y} set' % pos_xfrm_item)
		for key in range(len(light.yposkey)):
			makeKey(light.yposkey[key], light.yposval[key])
		lx.eval('select.channel {%s:pos.Z} set' % pos_xfrm_item)
		for key in range(len(light.zposkey)):
			makeKey(light.zposkey[key], light.zposval[key])

		# Rotation keys
		lx.eval('select.channel {%s:rot.Y} set' % rot_xfrm_item)
		for key in range(len(light.protkey)):
			makeKey(light.protkey[key], str_radians_to_degrees(light.protval[key]))
		lx.eval('select.channel {%s:rot.X} set' % rot_xfrm_item)
		for key in range(len(light.hrotkey)):
			makeKey(light.hrotkey[key], str_radians_to_degrees(light.hrotval[key]))
		lx.eval('select.channel {%s:rot.Z} set' % rot_xfrm_item)
		for key in range(len(light.brotkey)):
			makeKey(light.brotkey[key], str_radians_to_degrees(light.brotval[key]))

		# Scale keys
		lx.eval('select.channel {%s:scl.X} set' % scl_xfrm_item)
		for key in range(len(light.xsclkey)):
			makeKey(light.xsclkey[key], light.xsclval[key])
		lx.eval('select.channel {%s:scl.Y} set' % scl_xfrm_item)
		for key in range(len(light.ysclkey)):
			makeKey(light.ysclkey[key], light.ysclval[key])
		lx.eval('select.channel {%s:scl.Z} set' % scl_xfrm_item)
		for key in range(len(light.zsclkey)):
			makeKey(light.zsclkey[key], light.zsclval[key])

# Read out object/null properties and set properties in class
def parseObjects():
	global content
	global objects
	# Determine number of objects to process and corresponding lines
	objectLines = []
	objects = []
	lineCounter = 0
	object_targetitemID_LW = "0"
	object_parentitemID_LW = "0"
	lightIndex = -1 # sets to 0 with first light added :)
	for lineCounter in range(len(content)):
		if(content[lineCounter].startswith('LoadObjectLayer')):
			tempString = content[lineCounter].split(' ')
			objectLines.append(lineCounter)
		if(content[lineCounter].startswith('AddNullObject')):
			tempString = content[lineCounter].split(' ')
			# We need our ID here to handle parenting later.
			object_itemID_LW = tempString[1]
			objectLines.append(lineCounter)

	lx.out('Found %d objects to create' % len(objectLines))

	for objectNumber in range(len(objectLines)):
		startLine = objectLines[objectNumber]
		if (objectNumber != (len(objectLines) - 1)):
			endLine = objectLines[objectNumber + 1]
		else:
			for lineCounter in range(startLine, len(content)):
				if (content[lineCounter].startswith('AddLight')): # End of last object block.
					endLine = lineCounter

		temp = content[objectLines[objectNumber]].split(' ')
		if(temp[0] == 'LoadObjectLayer'):
			lwofile = temp[3]
			if (len(temp) > 4):
				for token in range(4, len(temp)):
					lwofile += (' ' + temp[token])
			# We need our ID here to handle parenting later.
			object_itemID_LW = temp[2]
			lwolayer = temp[1]
			isnull = False
		else:
			lwofile = temp[2]
			if (len(temp) > 3):
				for token in range(3, len(temp)):
					lwofile += (' ' + temp[token]) # We abuse this to hold our null name.
			# We need our ID here to handle parenting later.
			object_itemID_LW = temp[1]
			isnull = True

		lx.out(lwofile)

		object_parentitemID_LW = 0
		# Pick up any target and parent item IDs
		for lineCounter in range(startLine, endLine):
			if(content[lineCounter].startswith('ParentItem')):
				tempString = content[lineCounter].split(' ')
				object_parentitemID_LW = tempString[1]
			if(content[lineCounter].startswith('TargetItem')):
				tempString = content[lineCounter].split(' ')
				object_targetitemID_LW = tempString[1]
				break

		xpos_start, xpos_end = keyBlockExtract('xpos',startLine, endLine)
		xpos_keys = []
		xpos_vals = []
		animationExtract(xpos_start, xpos_end, xpos_keys, xpos_vals)

		ypos_start, ypos_end = keyBlockExtract('ypos',startLine, endLine)
		ypos_keys = []
		ypos_vals = []
		animationExtract(ypos_start, ypos_end, ypos_keys, ypos_vals)

		zpos_start, zpos_end = keyBlockExtract('zpos',startLine, endLine)
		zpos_keys = []
		zpos_vals = []
		animationExtract(zpos_start, zpos_end, zpos_keys, zpos_vals)

		hrot_start, hrot_end = keyBlockExtract('hrot',startLine, endLine)
		hrot_keys = []
		hrot_vals = []
		animationExtract(hrot_start, hrot_end, hrot_keys, hrot_vals)

		prot_start, prot_end = keyBlockExtract('prot',startLine, endLine)
		prot_keys = []
		prot_vals = []
		animationExtract(prot_start, prot_end, prot_keys, prot_vals)

		brot_start, brot_end = keyBlockExtract('brot',startLine, endLine)
		brot_keys = []
		brot_vals = []
		animationExtract(brot_start, brot_end, brot_keys, brot_vals)

		xscl_start, xscl_end = keyBlockExtract('xscl',startLine, endLine)
		xscl_keys = []
		xscl_vals = []
		animationExtract(xscl_start, xscl_end, xscl_keys, xscl_vals)

		yscl_start, yscl_end = keyBlockExtract('yscl',startLine, endLine)
		yscl_keys = []
		yscl_vals = []
		animationExtract(yscl_start, yscl_end, yscl_keys, yscl_vals)

		zscl_start, zscl_end = keyBlockExtract('zscl',startLine, endLine)
		zscl_keys = []
		zscl_vals = []
		animationExtract(zscl_start, zscl_end, zscl_keys, zscl_vals)

		# Create a new object instance in our list.

		objects.append(Object(lwofile, lwolayer, object_itemID_LW, isnull, object_parentitemID_LW, object_targetitemID_LW,
							xpos_keys, xpos_vals, ypos_keys, ypos_vals, zpos_keys, zpos_vals,
							hrot_keys, hrot_vals, prot_keys, prot_vals, brot_keys, brot_vals,
							xscl_keys, xscl_vals, yscl_keys, yscl_vals, zscl_keys, zscl_vals
							))

# Make our mesh items and locators and set them up to match LW configuration based on light class
def makeObjects():
	global objects
	global contentDir_LW
	for lwObject in objects:
		if (lwObject.isnull == True):
			# Add a locator
			lx.eval('item.create locator')
			lx.eval('item.name {%s}' % lwObject.lwofile)
		else:
			# Import our LWO. For this, we need some heavy lifting with the item IDs, for layered objects (filtering only mesh items).
			beforeImport = set(meshList())
			importLWO(lwObject.lwofile)
			afterImport = set(meshList())
			# Newly added mesh items below. Since we want to index with this, we need to convert to a list.
			newlyAdded = list(afterImport.difference(beforeImport))
			# We need to remove all layers except the one referenced in the LWO line.
			# There is a limitation here in that we can't handle discontinuous layers in the LWO (e.g. blank layers)
			# MODO imports LWO layers in-sequence - the populated layers are imported and get an incremented item ID.
			targetLayer = int(lwObject.lwolayer) - 1 # convert from 1-index to 0-index
			lx.eval('select.drop item')
			for item in range(len(newlyAdded)):
				if(item != targetLayer):
					lx.eval('select.item {%s}' % newlyAdded[item])
					lx.eval('item.delete')
			lx.eval('select.item {%s}' % newlyAdded[targetLayer])
		itemName = lx.eval('query sceneservice selection ? locator')
		lwObject.modoid = itemName

		# Add our LW ID for targeting/parenting later.
		lx.eval('item.tag string LWID %s' % lwObject.lwitemid)

		# Transform items
		lx.eval('transform.add pos')
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % itemName)
		lx.eval('transform.add rot')
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % itemName)
		lx.eval('transform.add scl')
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % itemName)
		pos_xfrm_item = lx.eval('query sceneservice item.xfrmPos ? {%s}' % itemName)
		rot_xfrm_item = lx.eval('query sceneservice item.xfrmRot ? {%s}' % itemName)
		scl_xfrm_item = lx.eval('query sceneservice item.xfrmScl ? {%s}' % itemName)

		# Position keys
		lx.eval('select.channel {%s:pos.X} set' % pos_xfrm_item)
		for key in range(len(lwObject.xposkey)):
			makeKey(lwObject.xposkey[key], lwObject.xposval[key])
		lx.eval('select.channel {%s:pos.Y} set' % pos_xfrm_item)
		for key in range(len(lwObject.yposkey)):
			makeKey(lwObject.yposkey[key], lwObject.yposval[key])
		lx.eval('select.channel {%s:pos.Z} set' % pos_xfrm_item)
		for key in range(len(lwObject.zposkey)):
			makeKey(lwObject.zposkey[key], lwObject.zposval[key])

		# Rotation keys
		lx.eval('select.channel {%s:rot.Y} set' % rot_xfrm_item)
		for key in range(len(lwObject.protkey)):
			makeKey(lwObject.protkey[key], str_radians_to_degrees(lwObject.protval[key]))
		lx.eval('select.channel {%s:rot.X} set' % rot_xfrm_item)
		for key in range(len(lwObject.hrotkey)):
			makeKey(lwObject.hrotkey[key], str_radians_to_degrees(lwObject.hrotval[key]))
		lx.eval('select.channel {%s:rot.Z} set' % rot_xfrm_item)
		for key in range(len(lwObject.brotkey)):
			makeKey(lwObject.brotkey[key], str_radians_to_degrees(lwObject.brotval[key]))

		# Scale keys
		lx.eval('select.channel {%s:scl.X} set' % scl_xfrm_item)
		for key in range(len(lwObject.xsclkey)):
			makeKey(lwObject.xsclkey[key], lwObject.xsclval[key])
		lx.eval('select.channel {%s:scl.Y} set' % scl_xfrm_item)
		for key in range(len(lwObject.ysclkey)):
			makeKey(lwObject.ysclkey[key], lwObject.ysclval[key])
		lx.eval('select.channel {%s:scl.Z} set' % scl_xfrm_item)
		for key in range(len(lwObject.zsclkey)):
			makeKey(lwObject.zsclkey[key], lwObject.zsclval[key])

# Read out camera properties and set properties in class
def parseCameras():
	global content
	global cameras
	# Determine number of cameras to process and corresponding lines
	cameraLines = []
	cameras = []
	lineCounter = 0
	camera_parentitemID_LW = "0"
	camera_targetitemID_LW = "0"
	cameraIndex = -1 # sets to 0 with first camera added :)
	for lineCounter in range(len(content)):
		if(content[lineCounter].startswith('AddCamera')):
			tempString = content[lineCounter].split(' ')
			cameraLines.append(lineCounter)
	lx.out('Found %d cameras to create' % len(cameraLines))

	# So now we need to work with the fixed camera structure. Only native cameras are supported in this parser.
	for cameraNumber in range(len(cameraLines)):
		startLine = cameraLines[cameraNumber]
		if (cameraNumber != (len(cameraLines) - 1)):
			endLine = cameraLines[cameraNumber + 1]
		else:
			for lineCounter in range(startLine, len(content)):
				if (content[lineCounter].startswith('Antialiasing')): # End of last camera block.
					endLine = lineCounter

		# We need our ID here to handle parenting later.
		camera_itemID_LW = extractValue(content[startLine])
		cameraName = extractValue(content[startLine + 1])

		camera_parentitemID_LW = 0
		# Pick up any target and parent item IDs
		for lineCounter in range(startLine, endLine):
			if(content[lineCounter].startswith('ParentItem')):
				tempString = content[lineCounter].split(' ')
				camera_parentitemID_LW = tempString[1]
			if(content[lineCounter].startswith('TargetItem')):
				tempString = content[lineCounter].split(' ')
				camera_targetitemID_LW = tempString[1]

		xpos_start, xpos_end = keyBlockExtract('xpos',startLine, endLine)
		xpos_keys = []
		xpos_vals = []
		animationExtract(xpos_start, xpos_end, xpos_keys, xpos_vals)

		ypos_start, ypos_end = keyBlockExtract('ypos',startLine, endLine)
		ypos_keys = []
		ypos_vals = []
		animationExtract(ypos_start, ypos_end, ypos_keys, ypos_vals)

		zpos_start, zpos_end = keyBlockExtract('zpos',startLine, endLine)
		zpos_keys = []
		zpos_vals = []
		animationExtract(zpos_start, zpos_end, zpos_keys, zpos_vals)

		hrot_start, hrot_end = keyBlockExtract('hrot',startLine, endLine)
		hrot_keys = []
		hrot_vals = []
		animationExtract(hrot_start, hrot_end, hrot_keys, hrot_vals)

		prot_start, prot_end = keyBlockExtract('prot',startLine, endLine)
		prot_keys = []
		prot_vals = []
		animationExtract(prot_start, prot_end, prot_keys, prot_vals)

		brot_start, brot_end = keyBlockExtract('brot',startLine, endLine)
		brot_keys = []
		brot_vals = []
		animationExtract(brot_start, brot_end, brot_keys, brot_vals)

		# Create a new camera instance in our list.
		cameras.append(Camera(cameraName, camera_itemID_LW, camera_parentitemID_LW, camera_targetitemID_LW,
							xpos_keys, xpos_vals, ypos_keys, ypos_vals, zpos_keys, zpos_vals,
							hrot_keys, hrot_vals, prot_keys, prot_vals, brot_keys, brot_vals
							))

# Make our cameras and set them up to match LW configuration based on light class
def makeCameras():
	global cameras
	for camera in cameras:
		lx.eval('!item.create camera')
		lx.eval('!item.name {%s}' % camera.name)

		# Add our LW ID for targeting/parenting later.
		lx.eval('!item.tag string LWID %s' % camera.lwitemid)

		cameraName = lx.eval('query sceneservice selection ? camera')
		camera.modoid = cameraName

		# Transform items
		lx.eval('transform.add pos')
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % cameraName)
		lx.eval('transform.add rot')
		lx.eval('select.drop item')
		lx.eval('select.item {%s}' % cameraName)
		pos_xfrm_item = lx.eval('query sceneservice item.xfrmPos ? {%s}' % cameraName)
		rot_xfrm_item = lx.eval('query sceneservice item.xfrmRot ? {%s}' % cameraName)

		# Position keys
		lx.eval('select.channel {%s:pos.X} set' % pos_xfrm_item)
		for key in range(len(camera.xposkey)):
			makeKey(camera.xposkey[key], camera.xposval[key])
		lx.eval('select.channel {%s:pos.Y} set' % pos_xfrm_item)
		for key in range(len(camera.yposkey)):
			makeKey(camera.yposkey[key], camera.yposval[key])
		lx.eval('select.channel {%s:pos.Z} set' % pos_xfrm_item)
		for key in range(len(camera.zposkey)):
			makeKey(camera.zposkey[key], camera.zposval[key])

		# Rotation keys
		lx.eval('select.channel {%s:rot.Y} set' % rot_xfrm_item)
		for key in range(len(camera.protkey)):
			makeKey(camera.protkey[key], str_radians_to_degrees(camera.protval[key]))
		lx.eval('select.channel {%s:rot.X} set' % rot_xfrm_item)
		for key in range(len(camera.hrotkey)):
			makeKey(camera.hrotkey[key], str_radians_to_degrees(camera.hrotval[key]))
		lx.eval('select.channel {%s:rot.Z} set' % rot_xfrm_item)
		for key in range(len(camera.brotkey)):
			makeKey(camera.brotkey[key], str_radians_to_degrees(camera.brotval[key]))

# Generate list of all mesh items in scene
def meshList():
	mList = []
	for i in range(lx.eval('query sceneservice item.N ?')):
	    type = lx.eval('query sceneservice item.type ? %s' % i)
	    if (type == "mesh"):
	    	mList.append(lx.eval('query sceneservice item.id ? %s' % i))
	return mList

# Generate list of all locator items in scene
def locatorList():
	lList = []
	for i in range(lx.eval('query sceneservice item.N ?')):
	    type = lx.eval('query sceneservice item.type ? %s' % i)
	    if (type == "locator"):
	    	lList.append(lx.eval('query sceneservice item.id ? %s' % i))
	return lList

# Generate list of all mesh and locator items in scene
def meshLocatorList():
	mList = meshList()
	lList = locatorList()
	return mList + lList

# Generate list of all camera items in scene
def cameraList():
	cList = []
	for i in range(lx.eval('query sceneservice item.N ?')):
	    type = lx.eval('query sceneservice item.type ? %s' % i)
	    if (type == "camera"):
	    	cList.append(lx.eval('query sceneservice item.id ? %s' % i))
	return cList

# Generate list of all light items in scene
def lightList():
	lList = []
	for i in range(lx.eval('query sceneservice item.N ?')):
	    type = lx.eval('query sceneservice item.type ? %s' % i)
	    if (type == "light"):
	    	lList.append(lx.eval('query sceneservice item.id ? %s' % i))
	return lList

# Set modo scene properties to align with LW scene properties.
def sceneProperties():
	firstFrame = int(extractValueFromSetting('FirstFrame'))
	lx.out(firstFrame)
	lastFrame = int(extractValueFromSetting('LastFrame'))
	lx.out(lastFrame)
	frameRate_LW = float(extractValueFromSetting('FramesPerSecond'))
	lx.out(frameRate_LW)

	# Set the modo scene framerate to match:
	lx.eval('time.fpsCustom %f' % frameRate_LW)
	# Set first frame
	tempVal = float(firstFrame/frameRate_LW)
	lx.eval('time.range scene %d ' % (tempVal))
	lx.eval('time.range current %d ' % (tempVal))
	# Set last frame
	tempVal = float(lastFrame/frameRate_LW)
	lx.eval('time.range scene out:%d ' % (tempVal))
	lx.eval('time.range current out:%d ' % (tempVal))

# Simple helper to set modo values
def setModoParameter(parameter, value):
	lx.eval('{%s} {%s}' % (parameter, value))

# Simple error handling.
def reportError(errorString):
	    lx.eval('dialog.setup error')
	    lx.eval('dialog.title {Something went wrong}')
	    lx.eval('dialog.msg {%s!}' % errorString)
	    lx.eval('dialog.open')
	    sys.exit()

# Simple helper to get value for a setting.
def extractValueFromSetting(settingString):
	global content
	value = extractValue(content[findSetting(settingString)])
	return value

# Simple helper to find a setting in the content[] array for the LW scene.
def findSetting(settingString):
	global content
	fsLineCounter = 0
	found = 0
	while (found == 0):
		if content[fsLineCounter].startswith(settingString):
			break
		fsLineCounter += 1
		if (fsLineCounter > len(content)):
			reportError('Parameter {%s} not found - aborting' % settingString)
	return fsLineCounter

# Simple helper to extract value for a parameter in the LW scene.
def extractValue(tempString):
	value = tempString.split(' ', 1)
	return value[1]

# Port of call for LWO loading
def importLWO(path):
	lx.out(path)
	path = validatePath(path)
	# Load referenced LWO from scene file.
	try:
		lx.eval('scene.open {%s} import' % path)
	except:
		# File import failed. Add an empty mesh and move on.
		lx.eval('item.create mesh')
		lx.eval('item.name {%s}' % path)

# Check path for validity and try to manage cases where the path is not correct (e.g. out of content folder, different platform)
def validatePath(path):
	global originalPathList
	global replacementPathList
	global contentDir_LW

	lx.out(path)
	validPath = os.path.isfile(contentDir_LW + os.sep + path)
	if (validPath == True):
		return(contentDir_LW + os.sep + path)
	else:
		# Mac LW can be very annoying. Let's see if we have such a case here.
		colonIndex = path.index(':')
		if (colonIndex > 2): # Mac does VolumeName:myDir/myFile.lwo, so the corresponding file would be /Volumes/VolumeName/myDir/myFile.lwo
			testPath = '/Volumes/' + string.replace(path,':','/',1)
			validPath = os.path.isfile(testPath)
		if (validPath == True):
			return testPath

		lastPathSep = path.rfind('\\')
		if (lastPathSep == -1): # Not found
			lastPathSep = path.rfind('/')

		separator = path[lastPathSep]
		workingReplacement = False

		# Let's check whether we have encountered this path before and have a potential replacement.
		try:
			# We can have more than one replacement path for a given original path. We'll need to check all cases as appropriate.
			# We look for each matching instance for the original path and then populate a replacement path temporary array for use later.
			rpTempArray = []
			for entry in range(len(originalPathList)):
				if (originalPathList[entry] == path[:lastPathSep]):
					rpTempArray.append(replacementPathList[entry])

			# Walk our replacement path temporary array to see if any instance delivers a valid path to our asset
			for entry in range(len(rpTempArray)):
				newPath = rpTempArray[entry] + os.sep + path[lastPathSep+1:]
				# Let's see if this is actually a valid file
				workingReplacement = os.path.isfile(newPath)
				if(workingReplacement == True):
					break
		except:
			pass

		if (workingReplacement == False):
			brokenObject = path[lastPathSep + 1:]
			replacementFileString = "Locate " + brokenObject
			newPath = customfile('fileOpen', replacementFileString, 'lwo', 'LWO', '*.lwo', contentDir_LW)
			if (newPath == None):
				reportError("Aborting since replacement path not defined")
				sys.exit()

			# First time encountering this path. Let's store it and the replacement in case we hit this again and can handle it cleanly.
			originalPathList.append(path[:lastPathSep])
			lastPathSep = newPath.rfind(os.sep)
			replacementPathList.append(newPath[:lastPathSep]) 

		return newPath

# Simple key creator for modo channels.
def makeKey(time,value):
	# Make key on channel at given time
	lx.eval('channel.key {%s} {%s} ' % (time, value) )

# Read out all of the key frames for a channel
def keyBlockExtract(channel, startline, endline):
	global content
	channel_label = ['xpos', 'ypos', 'zpos', 'hrot', 'prot', 'brot', 'xscl', 'yscl', 'zscl']
	start = -1
	end = -1
	channel_search_string = 'Channel ' + str(channel_label.index(channel))
	for lineCounter in range(startline, endline):
		if(content[lineCounter] == channel_search_string):
			start = lineCounter + 1
			break
	if(start == -1):
		reportError('Channel not found')
	else:
		for lineCounter in range(startline, endline):
			if(content[lineCounter] == '}'):
				end = lineCounter
				break
	if(end == -1):
		reportError('End marker not found for channel')
	return(start,end)

def animationExtract(startLine, endLine, keyarray, valuearray):
	global content
	''' Expecting a structure in content list like :
		Channel 0
		{ Envelope
		  2
		  Key -2 0 0 0 0 0 0 0 0
		  Key -4 0.033333333333333332871 0 0 0 0 -1.9834710743801653443 0 0
		  Behaviors 1 1
		}

		startLine should be { Envelope
		endLine should be }
	'''
	if (content[startLine] != '{ Envelope'):
		reportError('Start line not matched')
	if (content[endLine] != '}'):
		reportError('End line not matched')
	numberOfKeys = int(content[startLine + 1])
	lx.out('Found %d keys' % numberOfKeys)
	lineCounter = startLine + 2
	for i in range(numberOfKeys):
		tempLine = content[lineCounter]
		if(tempLine.startswith('  Key')):
			lineArray = content[lineCounter].split(' ')
			keyarray.append(lineArray[4])
			valuearray.append(lineArray[3])
			lx.out('Key %d : %s at time %s' % (i, lineArray[3], lineArray[4]))
		else:
			reportError('Key line not found')
		lineCounter += 1

# LW stores rotation in radians. Need to map to degrees for modo.
def str_radians_to_degrees(radians):
	return str((float(radians) * (180/math.pi)))

# Here's where we coordinate the work to build out the hierarchical structure by item
def buildHierarchy():
	global objects
	global lights
	global cameras

	# Build filtered lists to speed up searches
	meshLocatorList,lightList,cameraList = buildHierarchy_genParentLists()

	for lwObject in objects:
		buildHierarchy_doParenting(lwObject.modoid, lwObject.parentlwitemid, meshLocatorList,lightList,cameraList)

	for light in lights:
		buildHierarchy_doParenting(light.modoid, light.parentlwitemid, meshLocatorList,lightList,cameraList)

	for camera in cameras:
		buildHierarchy_doParenting(camera.modoid, camera.parentlwitemid, meshLocatorList,lightList,cameraList)

# Rebuild all of our lists by-type to optimize parent searches
def buildHierarchy_genParentLists():
	mlList = meshLocatorList()
	lList = lightList()
	cList = cameraList()
	return (mlList, lList,cList)

# Return the list of potential parents. LW prefixes each item ID with the genus of the item type. We can use this to our advantage.
def buildHierarchy_setParentList(parentID,meshLocatorList,lightList,cameraList):

	# Filter search to reduce runtime.
	if(parentID.startswith('1')):
		# Parent is an object or locator
		parentSearchList = meshLocatorList
	if(parentID.startswith('2')):
		# Parent is a light
		parentSearchList = lightList
	if(parentID.startswith('3')):
		# Parent is a camera
		parentSearchList = cameraList
	return parentSearchList

# Read out tags and values for the item.
def buildHierarchy_itemTags(item_name):
	item_tags = []
	temp = lx.evalN('query sceneservice item.tagTypes ? {%s} ' % item_name)
	for i in temp:
		item_tags.append(i)
	item_tagValues = []
	temp = []
	temp = lx.evalN('query sceneservice item.tags ? {%s} ' % item_name)
	for i in temp:
		item_tagValues.append(i)
	return (item_tags, item_tagValues)

# Heavy lifting for parenting by getting the list of potential parents and then walking it to find the item with the matching LWID tag for our parent item ID.
def buildHierarchy_doParenting(modo_itemid, lwparentitemid, meshLocatorList,lightList,cameraList):
	global parentSearchList
	if(lwparentitemid != 0):
		lx.out('item requests a parent of ID : {%s}' % lwparentitemid)
		# Get parent search list
		parentSearchList = buildHierarchy_setParentList(lwparentitemid,meshLocatorList,lightList,cameraList)
		lx.out('parentSearchList : {%s}' % parentSearchList)
		# Need to find our id in the modo scene.
		for item in parentSearchList:
			lx.eval('select.drop item')
			lx.eval('select.item {%s}' % item)
			item_name = lx.eval('item.name ?')
			item_tags, item_tagValues = buildHierarchy_itemTags(item_name)
			if (len(item_tags) != 0):
				lx.out("item tags found. Searching....")
				try :
					lwidIndex = item_tags.index('LWID')
				except:
					break
				lx.out('LWID tag found at : {%d} ' % lwidIndex)
				lwidValue = item_tagValues[lwidIndex]
				lx.out('LWID value : {%s} ' % lwidValue)
				if (lwidValue == lwparentitemid):
					parent_modoID = lx.eval('query sceneservice selection ? locator')
					lx.out('parent matched')
					# Need to select child and then parent using our IDs
					lx.eval('select.drop item')
					lx.eval('select.item {%s} set' % modo_itemid)
					lx.eval('select.item {%s} add' % parent_modoID)

					# Now parent.
					lx.eval('item.parent')
					lx.eval('select.drop item')
					break

# From Gwynne Reddick
def customfile(type, title, format, uname, ext, save_ext=None, path=None):
    '''
        Open a file requester for a custom file type and return result
        type - open or save dialog (fileOpen or fileSave)
        title - dialog title
        format - file format
        uname - format username
        ext - file extension in the form '*.ext'
        save_ext - (optional)
        path - (optional) Default path to open dialog with
        
        examples:
            file = customfile('fileOpen', 'Open JPEG file', 'JPG', 'JPEG File', '*.jpg;*.jpeg')
            file = customfile('fileSave', 'Save Text file', 'TXT', 'Text File', '*.txt', 'txt')
    
    '''
    lx.eval('dialog.setup %s' % type)
    lx.eval('dialog.title {%s}' % (title))
    lx.eval('dialog.fileTypeCustom {%s} {%s} {%s} {%s}' % (format, uname, ext, save_ext))
    if type == 'fileSave' and save_ext != None:
        lx.eval('dialog.fileSaveFormat %s' % save_ext)
    if path != None:
        lx.eval('dialog.result {%s}' % (path + 'Scenes'))
    try:
        lx.eval('dialog.open')
        return lx.eval('dialog.result ?')
    except:
        return None

	#stlfile = customfile('fileOpen', 'Load STL file', 'stl', 'STL', '*.stl')
'''
def get_xfrm_pos(item):
	try:
        posxfrm = lx.object.Locator(item).GetTransformItem(lx.symbol.iXFRM_POSITION)
    except:
        posxfrm = lx.object.Locator(item).AddTransformItem(lx.symbol.iXFRM_POSITION)[0]

def get_xfrm_rot(item):
	try:
        rotxfrm = lx.object.Locator(item).GetTransformItem(lx.symbol.iXFRM_ROTATION)
    except:
        rotxfrm = lx.object.Locator(item).AddTransformItem(lx.symbol.iXFRM_ROTATION)[0]
'''
main()
