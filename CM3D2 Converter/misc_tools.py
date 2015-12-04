import os, re, sys, bpy, time, bmesh, mathutils
from . import common

# アドオンアップデート処理
class update_cm3d2_converter(bpy.types.Operator):
	bl_idname = 'script.update_cm3d2_converter'
	bl_label = "CM3D2 Converterを更新"
	bl_description = "GitHubから最新版のCM3D2 Converterアドオンをダウンロードし上書き更新します"
	bl_options = {'REGISTER'}
	
	is_restart = bpy.props.BoolProperty(name="更新後にBlenderを再起動", default=True)
	is_toggle_console = bpy.props.BoolProperty(name="再起動後にコンソールを閉じる", default=True)
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.menu('INFO_MT_help_CM3D2_Converter_RSS', icon='INFO')
		self.layout.prop(self, 'is_restart', icon='BLENDER')
		self.layout.prop(self, 'is_toggle_console', icon='CONSOLE')
	
	def execute(self, context):
		import os, sys, urllib, zipfile, subprocess, urllib.request
		
		zip_path = os.path.join(bpy.app.tempdir, "Blender-CM3D2-Converter-master.zip")
		addon_path = os.path.dirname(__file__)
		
		response = urllib.request.urlopen("https://github.com/CM3Duser/Blender-CM3D2-Converter/archive/master.zip")
		zip_file = open(zip_path, "wb")
		zip_file.write(response.read())
		zip_file.close()
		
		zip_file = zipfile.ZipFile(zip_path, "r")
		for path in zip_file.namelist():
			if not os.path.basename(path):
				continue
			sub_dir = os.path.split( os.path.split(path)[0] )[1]
			if sub_dir == "CM3D2 Converter":
				file = open(os.path.join(addon_path, os.path.basename(path)), 'wb')
				file.write(zip_file.read(path))
				file.close()
		zip_file.close()
		
		if self.is_restart:
			filepath = bpy.data.filepath
			command_line = [sys.argv[0]]
			if filepath:
				command_line.append(filepath)
			if self.is_toggle_console:
				py = os.path.join(os.path.dirname(__file__), "console_toggle.py")
				command_line.append('-P')
				command_line.append(py)
			subprocess.Popen(command_line)
			bpy.ops.wm.quit_blender()
		else:
			self.report(type={'INFO'}, message="Blender-CM3D2-Converterを更新しました、再起動して下さい")
		return {'FINISHED'}

class quick_transfer_vertex_group(bpy.types.Operator):
	bl_idname = 'object.quick_transfer_vertex_group'
	bl_label = "クイック・ウェイト転送"
	bl_description = "アクティブなメッシュに他の選択メッシュの頂点グループを高速で転送します"
	bl_options = {'REGISTER', 'UNDO'}
	
	is_first_remove_all = bpy.props.BoolProperty(name="最初に全頂点グループを削除", default=True)
	is_remove_empty = bpy.props.BoolProperty(name="割り当てのない頂点グループを削除", default=True)
	
	@classmethod
	def poll(cls, context):
		active_ob = context.active_object
		obs = context.selected_objects
		if len(obs) != 2:
			return False
		for ob in obs:
			if ob.type != 'MESH':
				return False
			if ob.name != active_ob.name:
				if len(ob.vertex_groups):
					return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'is_first_remove_all', icon='ERROR')
		self.layout.prop(self, 'is_remove_empty', icon='X')
	
	def execute(self, context):
		import mathutils, time
		start_time = time.time()
		
		target_ob = context.active_object
		for ob in context.selected_objects:
			if ob.name != target_ob.name:
				source_ob = ob
				break
		target_me = target_ob.data
		source_me = source_ob.data
		
		pre_mode = target_ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		
		if self.is_first_remove_all:
			if len(target_ob.vertex_groups):
				bpy.ops.object.vertex_group_remove(all=True)
		
		kd = mathutils.kdtree.KDTree(len(source_me.vertices))
		for vert in source_me.vertices:
			co = source_ob.matrix_world * vert.co
			kd.insert(co, vert.index)
		kd.balance()
		
		near_vert_indexs = []
		for vert in target_me.vertices:
			target_co = target_ob.matrix_world * vert.co
			near_index = kd.find(target_co)[1]
			near_vert_indexs.append(near_index)
		
		context.window_manager.progress_begin(0, len(source_ob.vertex_groups))
		for source_vertex_group in source_ob.vertex_groups:
			
			if source_vertex_group.name in target_ob.vertex_groups.keys():
				target_vertex_group = target_ob.vertex_groups[source_vertex_group.name]
			else:
				target_vertex_group = target_ob.vertex_groups.new(source_vertex_group.name)
			
			is_waighted = False
			
			source_weights = []
			for source_vert in source_me.vertices:
				for elem in source_vert.groups:
					if elem.group == source_vertex_group.index:
						source_weights.append(elem.weight)
						break
				else:
					source_weights.append(0.0)
			
			for target_vert in target_me.vertices:
				
				near_vert_index = near_vert_indexs[target_vert.index]
				near_weight = source_weights[near_vert_index]
				
				if 0.01 < near_weight:
					target_vertex_group.add([target_vert.index], near_weight, 'REPLACE')
					is_waighted = True
				else:
					if not self.is_first_remove_all:
						target_vertex_group.remove([target_vert.index])
			
			context.window_manager.progress_update(source_vertex_group.index)
			
			if not is_waighted and self.is_remove_empty:
				target_ob.vertex_groups.remove(target_vertex_group)
		context.window_manager.progress_end()
		
		target_ob.vertex_groups.active_index = 0
		bpy.ops.object.mode_set(mode=pre_mode)
		
		diff_time = time.time() - start_time
		self.report(type={'INFO'}, message=str(round(diff_time, 1)) + " Seconds")
		return {'FINISHED'}

class precision_transfer_vertex_group(bpy.types.Operator):
	bl_idname = 'object.precision_transfer_vertex_group'
	bl_label = "高精度・ウェイト転送"
	bl_description = "アクティブなメッシュに他の選択メッシュの頂点グループを高精度で転送します"
	bl_options = {'REGISTER', 'UNDO'}
	
	is_first_remove_all = bpy.props.BoolProperty(name="最初に全頂点グループを削除", default=True)
	extend_range = bpy.props.FloatProperty(name="範囲倍率", default=2, min=1.1, max=5, soft_min=1.1, soft_max=5, step=10, precision=2)
	is_remove_empty = bpy.props.BoolProperty(name="割り当てのない頂点グループを削除", default=True)
	
	@classmethod
	def poll(cls, context):
		active_ob = context.active_object
		obs = context.selected_objects
		if len(obs) != 2:
			return False
		for ob in obs:
			if ob.type != 'MESH':
				return False
			if ob.name != active_ob.name:
				if len(ob.vertex_groups):
					return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'is_first_remove_all', icon='ERROR')
		self.layout.prop(self, 'extend_range', icon='META_EMPTY')
		self.layout.prop(self, 'is_remove_empty', icon='X')
	
	def execute(self, context):
		import mathutils, time
		start_time = time.time()
		
		target_ob = context.active_object
		for ob in context.selected_objects:
			if ob.name != target_ob.name:
				source_ob = ob
				break
		target_me = target_ob.data
		source_me = source_ob.data
		
		pre_mode = target_ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		
		if self.is_first_remove_all:
			if len(target_ob.vertex_groups):
				bpy.ops.object.vertex_group_remove(all=True)
		
		kd = mathutils.kdtree.KDTree(len(source_me.vertices))
		for vert in source_me.vertices:
			co = source_ob.matrix_world * vert.co
			kd.insert(co, vert.index)
		kd.balance()
		
		context.window_manager.progress_begin(0, len(target_me.vertices))
		progress_reduce = len(target_me.vertices) // 200 + 1
		near_vert_data = []
		near_vert_multi_total = []
		for vert in target_me.vertices:
			near_vert_data.append([])
			
			target_co = target_ob.matrix_world * vert.co
			
			mini_co, mini_index, mini_dist = kd.find(target_co)
			radius = mini_dist * self.extend_range
			diff_radius = radius - mini_dist
			
			multi_total = 0.0
			for co, index, dist in kd.find_range(target_co, radius):
				if 0 < diff_radius:
					multi = (diff_radius - (dist - mini_dist)) / diff_radius
				else:
					multi = 1.0
				near_vert_data[-1].append((index, multi))
				multi_total += multi
			near_vert_multi_total.append(multi_total)
			
			if vert.index % progress_reduce == 0:
				context.window_manager.progress_update(vert.index)
		context.window_manager.progress_end()
		
		context.window_manager.progress_begin(0, len(source_ob.vertex_groups))
		for source_vertex_group in source_ob.vertex_groups:
			
			if source_vertex_group.name in target_ob.vertex_groups.keys():
				target_vertex_group = target_ob.vertex_groups[source_vertex_group.name]
			else:
				target_vertex_group = target_ob.vertex_groups.new(source_vertex_group.name)
			
			is_waighted = False
			
			source_weights = []
			for source_vert in source_me.vertices:
				for elem in source_vert.groups:
					if elem.group == source_vertex_group.index:
						source_weights.append(elem.weight)
						break
				else:
					source_weights.append(0.0)
			
			for target_vert in target_me.vertices:
				
				if 0 < near_vert_multi_total[target_vert.index]:
					
					total_weight = 0.0
					
					for near_index, near_multi in near_vert_data[target_vert.index]:
						total_weight += source_weights[near_index] * near_multi
					
					average_weight = total_weight / near_vert_multi_total[target_vert.index]
				else:
					average_weight = 0.0
				
				if 0.01 < average_weight:
					target_vertex_group.add([target_vert.index], average_weight, 'REPLACE')
					is_waighted = True
				else:
					if not self.is_first_remove_all:
						target_vertex_group.remove([target_vert.index])
				
			context.window_manager.progress_update(source_vertex_group.index)
			
			if not is_waighted and self.is_remove_empty:
				target_ob.vertex_groups.remove(target_vertex_group)
		context.window_manager.progress_end()
		
		target_ob.vertex_groups.active_index = 0
		bpy.ops.object.mode_set(mode=pre_mode)
		
		diff_time = time.time() - start_time
		self.report(type={'INFO'}, message=str(round(diff_time, 1)) + " Seconds")
		return {'FINISHED'}

class blur_vertex_group(bpy.types.Operator):
	bl_idname = 'object.blur_vertex_group'
	bl_label = "頂点グループぼかし"
	bl_description = "アクティブ、もしくは全ての頂点グループをぼかします"
	bl_options = {'REGISTER', 'UNDO'}
	
	items = [
		('ACTIVE', "アクティブのみ", "", 1),
		('ALL', "全て", "", 2),
		]
	target = bpy.props.EnumProperty(items=items, name="対象", default='ACTIVE')
	radius = bpy.props.FloatProperty(name="範囲倍率", default=3, min=0.1, max=50, soft_min=0.1, soft_max=50, step=50, precision=2)
	strength = bpy.props.IntProperty(name="強さ", default=1, min=1, max=10, soft_min=1, soft_max=10)
	items = [
		('BOTH', "増減両方", "", 1),
		('ADD', "増加のみ", "", 2),
		('SUB', "減少のみ", "", 3),
		]
	effect = bpy.props.EnumProperty(items=items, name="ぼかし効果", default='BOTH')
	is_normalize = bpy.props.BoolProperty(name="他頂点グループも調節", default=True)
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			if ob.type == 'MESH':
				return bool(ob.vertex_groups.active)
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'target', icon='ACTION')
		self.layout.prop(self, 'radius', icon='META_EMPTY')
		self.layout.prop(self, 'strength', icon='ARROW_LEFTRIGHT')
		self.layout.prop(self, 'effect', icon='BRUSH_ADD')
		self.layout.prop(self, 'is_normalize', icon='ALIGN')
	
	def execute(self, context):
		import bmesh, mathutils
		ob = context.active_object
		me = ob.data
		
		pre_mode = ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		
		edge_lengths = []
		bm = bmesh.new()
		bm.from_mesh(me)
		for edge in bm.edges:
			edge_lengths.append(edge.calc_length())
		bm.free()
		edge_lengths.sort()
		average_edge_length = sum(edge_lengths) / len(edge_lengths)
		center_index = int( (len(edge_lengths) - 1) / 2.0 )
		average_edge_length = (average_edge_length + edge_lengths[center_index]) / 2
		radius = average_edge_length * self.radius
		
		context.window_manager.progress_begin(0, len(me.vertices))
		progress_reduce = len(me.vertices) // 200 + 1
		near_vert_data = []
		kd = mathutils.kdtree.KDTree(len(me.vertices))
		for vert in me.vertices:
			kd.insert(vert.co.copy(), vert.index)
		kd.balance()
		for vert in me.vertices:
			near_vert_data.append([])
			for co, index, dist in kd.find_range(vert.co, radius):
				multi = (radius - dist) / radius
				near_vert_data[-1].append((index, multi))
			if vert.index % progress_reduce == 0:
				context.window_manager.progress_update(vert.index)
		context.window_manager.progress_end()
		
		target_vertex_groups = []
		if self.target == 'ACTIVE':
			target_vertex_groups.append(ob.vertex_groups.active)
		else:
			for vertex_group in ob.vertex_groups:
				target_vertex_groups.append(vertex_group)
		
		progress_total = len(target_vertex_groups) * self.strength * len(me.vertices)
		context.window_manager.progress_begin(0, progress_total)
		progress_reduce = progress_total // 200 + 1
		progress_count = 0
		for vertex_group in target_vertex_groups:
			for strength_count in range(self.strength):
				
				weights = []
				for vert in me.vertices:
					for elem in vert.groups:
						if elem.group == vertex_group.index:
							weights.append(elem.weight)
							break
					else:
						weights.append(0.0)
				
				for vert in me.vertices:
					
					target_weight = weights[vert.index]
					
					total_weight = 0.0
					total_multi = 0.0
					for index, multi in near_vert_data[vert.index]:
						if self.effect == 'ADD':
							if target_weight <= weights[index]:
								total_weight += weights[index] * multi
								total_multi += multi
						elif self.effect == 'SUB':
							if weights[index] <= target_weight:
								total_weight += weights[index] * multi
								total_multi += multi
						else:
							total_weight += weights[index] * multi
							total_multi += multi
					
					if 0 < total_multi:
						average_weight = total_weight / total_multi
					else:
						average_weight = 0.0
					
					if 0.001 < average_weight:
						vertex_group.add([vert.index], average_weight, 'REPLACE')
						print('rep')
					else:
						vertex_group.remove([vert.index])
					
					progress_count += 1
					if progress_count % progress_reduce == 0:
						context.window_manager.progress_update(progress_count)
					
					if self.is_normalize:
						
						other_weight_total = 0.0
						for elem in vert.groups:
							if elem.group != vertex_group.index:
								other_weight_total += elem.weight
						
						diff_weight = average_weight - target_weight
						new_other_weight_total = other_weight_total - diff_weight
						if 0 < other_weight_total:
							other_weight_multi = new_other_weight_total / other_weight_total
						else:
							other_weight_multi = 0.0
						
						for elem in vert.groups:
							if elem.group != vertex_group.index:
								vg = ob.vertex_groups[elem.group]
								vg.add([vert.index], elem.weight * other_weight_multi, 'REPLACE')
		
		context.window_manager.progress_end()
		bpy.ops.object.mode_set(mode=pre_mode)
		return {'FINISHED'}

class multiply_vertex_group(bpy.types.Operator):
	bl_idname = 'object.multiply_vertex_group'
	bl_label = "頂点グループに乗算"
	bl_description = "頂点グループのウェイトに数値を乗算し、ウェイトの強度を増減させます"
	bl_options = {'REGISTER', 'UNDO'}
	
	value = bpy.props.FloatProperty(name="倍率", default=1.1, min=0.1, max=10, soft_min=0.1, soft_max=10, step=10, precision=2)
	is_normalize = bpy.props.BoolProperty(name="他頂点グループも調節", default=True)
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			if ob.type == 'MESH':
				return bool(ob.vertex_groups.active)
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'value', icon='ARROW_LEFTRIGHT')
		self.layout.prop(self, 'is_normalize', icon='ALIGN')
	
	def execute(self, context):
		ob = context.active_object
		me = ob.data
		vertex_group = ob.vertex_groups.active
		
		pre_mode = ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		
		for vert in me.vertices:
			
			old_weight = -1
			other_weight_total = 0.0
			for elem in vert.groups:
				if elem.group == vertex_group.index:
					old_weight = elem.weight
				else:
					other_weight_total += elem.weight
			if old_weight == -1:
				continue
			
			new_weight = old_weight * self.value
			vertex_group.add([vert.index], new_weight, 'REPLACE')
			
			if self.is_normalize:
				
				diff_weight = new_weight - old_weight
				
				new_other_weight_total = other_weight_total - diff_weight
				if 0 < other_weight_total:
					other_weight_multi = new_other_weight_total / other_weight_total
				else:
					other_weight_multi = 0.0
				
				for elem in vert.groups:
					if elem.group != vertex_group.index:
						vg = ob.vertex_groups[elem.group]
						vg.add([vert.index], elem.weight * other_weight_multi, 'REPLACE')
		
		bpy.ops.object.mode_set(mode=pre_mode)
		return {'FINISHED'}

class decode_cm3d2_vertex_group_names(bpy.types.Operator):
	bl_idname = 'object.decode_cm3d2_vertex_group_names'
	bl_label = "頂点グループ名をCM3D2用→Blender用に変換"
	bl_description = "CM3D2で使われてるボーン名(頂点グループ名)をBlenderで左右対称編集できるように変換します"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		import re
		ob = context.active_object
		if ob:
			if ob.type == 'MESH':
				if ob.vertex_groups.active:
					for vg in ob.vertex_groups:
						if re.search(r'[_ ]([rRlL])[_ ]', vg.name):
							return True
		return False
	
	def execute(self, context):
		ob = context.active_object
		me = ob.data
		convert_count = 0
		context.window_manager.progress_begin(0, len(ob.vertex_groups))
		for vg_index, vg in enumerate(ob.vertex_groups[:]):
			context.window_manager.progress_update(vg_index)
			vg_name = common.decode_bone_name(vg.name)
			if vg_name != vg.name:
				if vg_name in ob.vertex_groups.keys():
					target_vg = ob.vertex_groups[vg_name]
					for vert in me.vertices:
						try:
							weight = vg.weight(vert.index)
						except:
							weight = 0.0
						try:
							target_weight = target_vg.weight(vert.index)
						except:
							target_weight = 0.0
						if 0.0 < weight + target_weight:
							target_vg.add([vert.index], weight + target_weight, 'REPLACE')
					ob.vertex_groups.remove(vg)
				else:
					vg.name = vg_name
				convert_count += 1
		if convert_count == 0:
			self.report(type={'WARNING'}, message="変換できる名前が見つかりませんでした")
		else:
			self.report(type={'INFO'}, message="頂点グループ名をBlender用に変換しました")
		context.window_manager.progress_end()
		return {'FINISHED'}

class encode_cm3d2_vertex_group_names(bpy.types.Operator):
	bl_idname = 'object.encode_cm3d2_vertex_group_names'
	bl_label = "頂点グループ名をBlender用→CM3D2用に変換"
	bl_description = "CM3D2で使われてるボーン名(頂点グループ名)に戻します"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		import re
		ob = context.active_object
		if ob:
			if ob.type == 'MESH':
				if ob.vertex_groups.active:
					for vg in ob.vertex_groups:
						if vg.name.count('*') == 1:
							if re.search(r'\.([rRlL])$', vg.name):
								return True
		return False
	
	def execute(self, context):
		ob = context.active_object
		me = ob.data
		convert_count = 0
		context.window_manager.progress_begin(0, len(ob.vertex_groups))
		for vg_index, vg in enumerate(ob.vertex_groups[:]):
			context.window_manager.progress_update(vg_index)
			vg_name = common.encode_bone_name(vg.name)
			if vg_name != vg.name:
				if vg_name in ob.vertex_groups.keys():
					target_vg = ob.vertex_groups[vg_name]
					for vert in me.vertices:
						try:
							weight = vg.weight(vert.index)
						except:
							weight = 0.0
						try:
							target_weight = target_vg.weight(vert.index)
						except:
							target_weight = 0.0
						if 0.0 < weight + target_weight:
							target_vg.add([vert.index], weight + target_weight, 'REPLACE')
					ob.vertex_groups.remove(vg)
				else:
					vg.name = vg_name
				convert_count += 1
		if convert_count == 0:
			self.report(type={'WARNING'}, message="変換できる名前が見つかりませんでした")
		else:
			self.report(type={'INFO'}, message="頂点グループ名をCM3D2用に戻しました")
		context.window_manager.progress_end()
		return {'FINISHED'}

class quick_shape_key_transfer(bpy.types.Operator):
	bl_idname = 'object.quick_shape_key_transfer'
	bl_label = "クイック・シェイプキー転送"
	bl_description = "アクティブなメッシュに他の選択メッシュのシェイプキーを高速で転送します"
	bl_options = {'REGISTER', 'UNDO'}
	
	is_first_remove_all = bpy.props.BoolProperty(name="最初に全シェイプキーを削除", default=True)
	is_remove_empty = bpy.props.BoolProperty(name="変形のないシェイプキーを削除", default=True)
	
	@classmethod
	def poll(cls, context):
		active_ob = context.active_object
		obs = context.selected_objects
		if len(obs) != 2:
			return False
		for ob in obs:
			if ob.type != 'MESH':
				return False
			if ob.name != active_ob.name:
				if ob.data.shape_keys:
					return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'is_first_remove_all', icon='ERROR')
		self.layout.prop(self, 'is_remove_empty', icon='X')
	
	def execute(self, context):
		import mathutils, time
		start_time = time.time()
		
		target_ob = context.active_object
		for ob in context.selected_objects:
			if ob.name != target_ob.name:
				source_ob = ob
				break
		target_me = target_ob.data
		source_me = source_ob.data
		
		pre_mode = target_ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		
		if self.is_first_remove_all:
			try:
				target_ob.active_shape_key_index = 1
				bpy.ops.object.shape_key_remove(all=True)
			except:
				pass
		
		kd = mathutils.kdtree.KDTree(len(source_me.vertices))
		for vert in source_me.vertices:
			co = source_ob.matrix_world * vert.co
			kd.insert(co, vert.index)
		kd.balance()
		
		near_vert_indexs = []
		for vert in target_me.vertices:
			target_co = target_ob.matrix_world * vert.co
			near_index = kd.find(target_co)[1]
			near_vert_indexs.append(near_index)
		
		is_shapeds = {}
		relative_keys = []
		context.window_manager.progress_begin(0, len(source_me.shape_keys.key_blocks))
		context.window_manager.progress_update(0)
		for source_shape_key_index, source_shape_key in enumerate(source_me.shape_keys.key_blocks):
			
			if target_me.shape_keys:
				if source_shape_key.name in target_me.shape_keys.key_blocks.keys():
					target_shape_key = target_ob.shape_keys.key_blocks[source_shape_key.name]
				else:
					target_shape_key = target_ob.shape_key_add(name=source_shape_key.name, from_mix=False)
			else:
				target_shape_key = target_ob.shape_key_add(name=source_shape_key.name, from_mix=False)
			
			relative_key_name = source_shape_key.relative_key.name
			if relative_key_name not in relative_keys:
				relative_keys.append(relative_key_name)
			is_shapeds[source_shape_key.name] = False
			
			try:
				target_shape_key.relative_key = target_me.shape_keys.key_blocks[relative_key_name]
			except:
				pass
			
			source_shape_keys = []
			for source_vert in source_me.vertices:
				shape_key_co = source_ob.matrix_world * source_shape_key.data[source_vert.index].co * target_ob.matrix_world
				vert_co = source_ob.matrix_world * source_me.vertices[source_vert.index].co * target_ob.matrix_world
				source_shape_keys.append(shape_key_co - vert_co)
			
			for target_vert in target_me.vertices:
				
				near_vert_index = near_vert_indexs[target_vert.index]
				near_shape_co = source_shape_keys[near_vert_index]
				
				target_shape_key.data[target_vert.index].co = target_me.vertices[target_vert.index].co + near_shape_co
				if 0.01 < near_shape_co.length:
					is_shapeds[source_shape_key.name] = True
			
			context.window_manager.progress_update(source_shape_key_index)
		context.window_manager.progress_end()
		
		if self.is_remove_empty:
			for source_shape_key_name, is_shaped in is_shapeds.items():
				if source_shape_key_name not in relative_keys and not is_shaped:
					target_shape_key = target_me.shape_keys.key_blocks[source_shape_key_name]
					target_ob.shape_key_remove(target_shape_key)
		
		target_ob.active_shape_key_index = 0
		bpy.ops.object.mode_set(mode=pre_mode)
		
		diff_time = time.time() - start_time
		self.report(type={'INFO'}, message=str(round(diff_time, 1)) + " Seconds")
		return {'FINISHED'}

class precision_shape_key_transfer(bpy.types.Operator):
	bl_idname = 'object.precision_shape_key_transfer'
	bl_label = "高精度・シェイプキー転送"
	bl_description = "アクティブなメッシュに他の選択メッシュのシェイプキーを高精度で転送します"
	bl_options = {'REGISTER', 'UNDO'}
	
	is_first_remove_all = bpy.props.BoolProperty(name="最初に全シェイプキーを削除", default=True)
	extend_range = bpy.props.FloatProperty(name="範囲倍率", default=2, min=1.1, max=5, soft_min=1.1, soft_max=5, step=10, precision=2)
	is_remove_empty = bpy.props.BoolProperty(name="変形のないシェイプキーを削除", default=True)
	
	@classmethod
	def poll(cls, context):
		active_ob = context.active_object
		obs = context.selected_objects
		if len(obs) != 2:
			return False
		for ob in obs:
			if ob.type != 'MESH':
				return False
			if ob.name != active_ob.name:
				if ob.data.shape_keys:
					return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'is_first_remove_all', icon='ERROR')
		self.layout.prop(self, 'extend_range', icon='META_EMPTY')
		self.layout.prop(self, 'is_remove_empty', icon='X')
	
	def execute(self, context):
		import mathutils, time
		start_time = time.time()
		
		target_ob = context.active_object
		for ob in context.selected_objects:
			if ob.name != target_ob.name:
				source_ob = ob
				break
		target_me = target_ob.data
		source_me = source_ob.data
		
		pre_mode = target_ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		
		if self.is_first_remove_all:
			try:
				target_ob.active_shape_key_index = 1
				bpy.ops.object.shape_key_remove(all=True)
			except:
				pass
		
		kd = mathutils.kdtree.KDTree(len(source_me.vertices))
		for vert in source_me.vertices:
			co = source_ob.matrix_world * vert.co
			kd.insert(co, vert.index)
		kd.balance()
		
		context.window_manager.progress_begin(0, len(target_me.vertices))
		progress_reduce = len(target_me.vertices) // 200 + 1
		near_vert_data = []
		near_vert_multi_total = []
		for vert in target_me.vertices:
			near_vert_data.append([])
			
			target_co = target_ob.matrix_world * vert.co
			mini_co, mini_index, mini_dist = kd.find(target_co)
			radius = mini_dist * self.extend_range
			diff_radius = radius - mini_dist
			
			multi_total = 0.0
			for co, index, dist in kd.find_range(target_co, radius):
				if 0 < diff_radius:
					multi = (diff_radius - (dist - mini_dist)) / diff_radius
				else:
					multi = 1.0
				near_vert_data[-1].append((index, multi))
				multi_total += multi
			near_vert_multi_total.append(multi_total)
			
			if vert.index % progress_reduce == 0:
				context.window_manager.progress_update(vert.index)
		context.window_manager.progress_end()
		
		is_shapeds = {}
		relative_keys = []
		context.window_manager.progress_begin(0, len(source_me.shape_keys.key_blocks))
		context.window_manager.progress_update(0)
		for source_shape_key_index, source_shape_key in enumerate(source_me.shape_keys.key_blocks):
			
			if target_me.shape_keys:
				if source_shape_key.name in target_me.shape_keys.key_blocks.keys():
					target_shape_key = target_ob.shape_keys.key_blocks[source_shape_key.name]
				else:
					target_shape_key = target_ob.shape_key_add(name=source_shape_key.name, from_mix=False)
			else:
				target_shape_key = target_ob.shape_key_add(name=source_shape_key.name, from_mix=False)
			
			relative_key_name = source_shape_key.relative_key.name
			if relative_key_name not in relative_keys:
				relative_keys.append(relative_key_name)
			is_shapeds[source_shape_key.name] = False
			
			try:
				target_shape_key.relative_key = target_me.shape_keys.key_blocks[relative_key_name]
			except:
				pass
			
			source_shape_keys = []
			for source_vert in source_me.vertices:
				shape_key_co = source_ob.matrix_world * source_shape_key.data[source_vert.index].co * target_ob.matrix_world
				vert_co = source_ob.matrix_world * source_me.vertices[source_vert.index].co * target_ob.matrix_world
				source_shape_keys.append(shape_key_co - vert_co)
			
			for target_vert in target_me.vertices:
				
				if 0 < near_vert_multi_total[target_vert.index]:
					
					total_diff_co = mathutils.Vector((0, 0, 0))
					
					for near_index, near_multi in near_vert_data[target_vert.index]:
						total_diff_co += source_shape_keys[near_index] * near_multi
					
					average_diff_co = total_diff_co / near_vert_multi_total[target_vert.index]
				
				else:
					average_diff_co = mathutils.Vector((0, 0, 0))
				
				target_shape_key.data[target_vert.index].co = target_me.vertices[target_vert.index].co + average_diff_co
				if 0.01 < average_diff_co.length:
					is_shapeds[source_shape_key.name] = True
			
			context.window_manager.progress_update(source_shape_key_index)
		context.window_manager.progress_end()
		
		if self.is_remove_empty:
			for source_shape_key_name, is_shaped in is_shapeds.items():
				if source_shape_key_name not in relative_keys and not is_shaped:
					target_shape_key = target_me.shape_keys.key_blocks[source_shape_key_name]
					target_ob.shape_key_remove(target_shape_key)
		
		target_ob.active_shape_key_index = 0
		bpy.ops.object.mode_set(mode=pre_mode)
		
		diff_time = time.time() - start_time
		self.report(type={'INFO'}, message=str(round(diff_time, 1)) + " Seconds")
		return {'FINISHED'}

class multiply_shape_key(bpy.types.Operator):
	bl_idname = 'object.multiply_shape_key'
	bl_label = "シェイプキーの変形に乗算"
	bl_description = "シェイプキーの変形に数値を乗算し、変形の強度を増減させます"
	bl_options = {'REGISTER', 'UNDO'}
	
	multi = bpy.props.FloatProperty(name="倍率", description="シェイプキーの拡大率です", default=1.1, min=-10, max=10, soft_min=-10, soft_max=10, step=10, precision=2)
	items = [
		('ACTIVE', "アクティブのみ", "", 1),
		('ALL', "全て", "", 2),
		]
	mode = bpy.props.EnumProperty(items=items, name="対象", default='ACTIVE')
	
	@classmethod
	def poll(cls, context):
		if context.active_object:
			ob = context.active_object
			if ob.type == 'MESH':
				if ob.active_shape_key:
					return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'multi', icon='ARROW_LEFTRIGHT')
		self.layout.prop(self, 'mode', icon='ACTION')
	
	def execute(self, context):
		ob = context.active_object
		me = ob.data
		shape_keys = me.shape_keys
		pre_mode = ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		if self.mode == 'ACTIVE':
			target_shapes = [ob.active_shape_key]
		elif self.mode == 'ALL':
			target_shapes = []
			for key_block in shape_keys.key_blocks:
				target_shapes.append(key_block)
		for shape in target_shapes:
			data = shape.data
			for i, vert in enumerate(me.vertices):
				diff = data[i].co - vert.co
				diff *= self.multi
				data[i].co = vert.co + diff
		bpy.ops.object.mode_set(mode=pre_mode)
		return {'FINISHED'}

class blur_shape_key(bpy.types.Operator):
	bl_idname = 'object.blur_shape_key'
	bl_label = "シェイプキーぼかし"
	bl_description = "シェイプキーの変形をぼかしてスムーズにします"
	bl_options = {'REGISTER', 'UNDO'}
	
	items = [
		('ACTIVE', "アクティブのみ", "", 1),
		('ALL', "全て", "", 2),
		]
	mode = bpy.props.EnumProperty(items=items, name="対象シェイプキー", default='ACTIVE')
	strength = bpy.props.IntProperty(name="処理回数", description="ぼかしの強度(回数)を設定します", default=5, min=1, max=100, soft_min=1, soft_max=100, step=1)
	items = [
		('BOTH', "増減両方", "", 1),
		('ADD', "増加のみ", "", 2),
		('SUB', "減少のみ", "", 3),
		]
	effect = bpy.props.EnumProperty(items=items, name="ぼかし効果", default='BOTH')
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			return ob.type=='MESH' and ob.active_shape_key
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'mode')
		self.layout.prop(self, 'strength')
		self.layout.prop(self, 'effect')
	
	def execute(self, context):
		import bmesh, mathutils
		ob = context.active_object
		me = ob.data
		shape_keys = me.shape_keys
		
		bm = bmesh.new()
		bm.from_mesh(me)
		
		pre_mode = ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		
		if self.mode == 'ACTIVE':
			target_shapes = [ob.active_shape_key]
		elif self.mode == 'ALL':
			target_shapes = []
			for key_block in shape_keys.key_blocks:
				target_shapes.append(key_block)
		context.window_manager.progress_begin(0, len(bm.verts) * len(target_shapes) * self.strength)
		
		near_vert_index = []
		for vert_index, vert in enumerate(bm.verts):
			near_vert_index.append([])
			for edge in vert.link_edges:
				for v in edge.verts:
					if vert_index != v.index:
						near_vert_index[-1].append(v.index)
		
		total_count = 0
		for strength_count in range(self.strength):
			for shape in target_shapes:
				data = shape.data
				new_co = []
				for vert_index, vert in enumerate(bm.verts):
					context.window_manager.progress_update(total_count)
					total_count += 1
					
					source_diff_co = data[vert_index].co - vert.co
					
					average_co = mathutils.Vector((0, 0, 0))
					average_total = 0
					for index in near_vert_index[vert_index]:
						diff_co = data[index].co - me.vertices[index].co
						
						if self.effect == 'ADD':
							if source_diff_co.length < diff_co.length:
								average_co += diff_co
								average_total += 1
						elif self.effect == 'SUB':
							if diff_co.length < source_diff_co.length:
								average_co += diff_co
								average_total += 1
						else:
							average_co += diff_co
							average_total += 1
					
					if 0 < average_total:
						average_co /= average_total
						new_co.append(((source_diff_co * 2) + average_co) / 3 + vert.co)
					else:
						new_co.append(source_diff_co + vert.co)
				for i, co in enumerate(new_co):
					data[i].co = co.copy()
		
		bpy.ops.object.mode_set(mode=pre_mode)
		context.window_manager.progress_end()
		return {'FINISHED'}

class radius_blur_shape_key(bpy.types.Operator):
	bl_idname = 'object.radius_blur_shape_key'
	bl_label = "シェイプキー範囲ぼかし"
	bl_description = "シェイプキーの変形を一定範囲の頂点でぼかしてスムーズにします"
	bl_options = {'REGISTER', 'UNDO'}
	
	items = [
		('ACTIVE', "アクティブのみ", "", 1),
		('ALL', "全て", "", 2),
		]
	mode = bpy.props.EnumProperty(items=items, name="対象シェイプキー", default='ACTIVE')
	blur_count = bpy.props.IntProperty(name="処理回数", default=1, min=1, max=100, soft_min=1, soft_max=100, step=1)
	items = [
		('BOTH', "増減両方", "", 1),
		('ADD', "増加のみ", "", 2),
		('SUB', "減少のみ", "", 3),
		]
	effect = bpy.props.EnumProperty(items=items, name="ぼかし効果", default='BOTH')
	radius_multi = bpy.props.FloatProperty(name="範囲：辺の長さの平均×", default=2, min=0.1, max=10, soft_min=0.1, soft_max=10, step=100, precision=1)
	is_shaped_radius = bpy.props.BoolProperty(name="モーフ変形後の範囲", default=False)
	fadeout = bpy.props.BoolProperty(name="距離で影響減退", default=True)
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			return ob.type=='MESH' and ob.active_shape_key
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'mode')
		self.layout.prop(self, 'blur_count')
		self.layout.prop(self, 'effect')
		self.layout.prop(self, 'radius_multi')
		self.layout.prop(self, 'is_shaped_radius')
		self.layout.prop(self, 'fadeout')
	
	def execute(self, context):
		import bmesh, mathutils
		ob = context.active_object
		me = ob.data
		
		bm = bmesh.new()
		bm.from_mesh(me)
		total_len = 0.0
		for edge in bm.edges:
			total_len += edge.calc_length()
		radius = (total_len / len(bm.edges)) * self.radius_multi
		bm.free()
		
		shape_keys = me.shape_keys
		pre_mode = ob.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		if self.mode == 'ACTIVE':
			target_shapes = [ob.active_shape_key]
		elif self.mode == 'ALL':
			target_shapes = []
			for key_block in shape_keys.key_blocks:
				target_shapes.append(key_block)
		
		if not self.is_shaped_radius:
			kd = mathutils.kdtree.KDTree(len(me.vertices))
			for i, v in enumerate(me.vertices):
				kd.insert(v.co, i)
			kd.balance()
			
			near_verts = []
			for vert in me.vertices:
				near_verts.append([])
				for co, index, dist in kd.find_range(vert.co, radius):
					diff = vert.co - co
					multi = (radius - diff.length) / radius
					near_verts[-1].append((index, multi))
		
		context.window_manager.progress_begin(0, self.blur_count * len(target_shapes) * len(me.vertices))
		total_count = 0
		for count in range(self.blur_count):
			for shape in target_shapes:
				data = shape.data
				
				if self.is_shaped_radius:
					kd = mathutils.kdtree.KDTree(len(me.vertices))
					for i, v in enumerate(data):
						kd.insert(v.co, i)
					kd.balance()
					near_verts = []
				
				new_co = []
				for vert in me.vertices:
					context.window_manager.progress_update(total_count)
					total_count += 1
					
					if self.is_shaped_radius:
						near_verts.append([])
						for co, index, dist in kd.find_range(data[vert.index].co, radius):
							diff = data[vert.index].co - co
							multi = (radius - diff.length) / radius
							near_verts[-1].append((index, multi))
					
					source_diff_co = data[vert.index].co - vert.co
					
					average_co = mathutils.Vector((0, 0, 0))
					nears_total = 0
					for index, multi in near_verts[vert.index]:
						diff_co = data[index].co - me.vertices[index].co
						if self.fadeout:
							if self.effect == 'ADD':
								if source_diff_co.length < diff_co.length:
									average_co += diff_co * multi
									nears_total += multi
							elif self.effect == 'SUB':
								if diff_co.length < source_diff_co.length:
									average_co += diff_co * multi
									nears_total += multi
							else:
								average_co += diff_co * multi
								nears_total += multi
						else:
							if self.effect == 'ADD':
								if source_diff_co.length < diff_co.length:
									average_co += diff_co
									nears_total += 1
							elif self.effect == 'SUB':
								if diff_co.length < source_diff_co.length:
									average_co += diff_co
									nears_total += 1
							else:
								average_co += diff_co
								nears_total += 1
					
					if 0 < nears_total:
						average_co /= nears_total
						new_co.append(((source_diff_co * 2) + average_co) / 3 + vert.co)
					else:
						new_co.append(source_diff_co + vert.co)
				for i, co in enumerate(new_co):
					data[i].co = co.copy()
		bpy.ops.object.mode_set(mode=pre_mode)
		context.window_manager.progress_end()
		return {'FINISHED'}

class new_cm3d2(bpy.types.Operator):
	bl_idname = 'material.new_cm3d2'
	bl_label = "CM3D2用マテリアルを新規作成"
	bl_description = "Blender-CM3D2-Converterで使用できるマテリアルを新規で作成します"
	bl_options = {'REGISTER', 'UNDO'}
	
	items = [
		('CM3D2/Toony_Lighted', "トゥーン", "", 0),
		('CM3D2/Toony_Lighted_Hair', "トゥーン 髪", "", 1),
		('CM3D2/Toony_Lighted_Trans', "トゥーン 透過", "", 2),
		('CM3D2/Toony_Lighted_Trans_NoZ', "トゥーン 透過 NoZ", "", 3),
		('CM3D2/Toony_Lighted_Outline', "トゥーン 輪郭線", "", 4),
		('CM3D2/Toony_Lighted_Hair_Outline', "トゥーン 輪郭線 髪", "", 5),
		('CM3D2/Toony_Lighted_Outline_Trans', "トゥーン 輪郭線 透過", "", 6),
		('CM3D2/Lighted_Trans', "透過", "", 7),
		('Unlit/Texture', "発光", "", 8),
		('Unlit/Transparent', "発光 透過", "", 9),
		('CM3D2/Mosaic', "モザイク", "", 10),
		('CM3D2/Man', "ご主人様", "", 11),
		('Diffuse', "リアル", "", 12),
		]
	type = bpy.props.EnumProperty(items=items, name="種類", default='CM3D2/Toony_Lighted_Outline')
	is_decorate = bpy.props.BoolProperty(name="種類に合わせてマテリアルを装飾", default=True)
	is_replace_cm3d2_tex = bpy.props.BoolProperty(name="テクスチャを探す", default=False, description="CM3D2本体のインストールフォルダからtexファイルを探して開きます")
	
	@classmethod
	def poll(cls, context):
		if 'material' in dir(context):
			if not context.material:
				return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		import re
		if not re.search(r'^[^\.]+\.[^\.]+$', common.remove_serial_number(context.active_object.name)):
			self.layout.label(text="オブジェクト名を設定してからの作成を推奨", icon='CANCEL')
		self.layout.separator()
		self.layout.prop(self, 'type', icon='ANTIALIASED')
		self.layout.prop(self, 'is_decorate', icon='TEXTURE_SHADED')
		self.layout.prop(self, 'is_replace_cm3d2_tex', icon='BORDERMOVE')
	
	def execute(self, context):
		ob = context.active_object
		ob_names = common.remove_serial_number(ob.name).split('.')
		if not context.material_slot:
			bpy.ops.object.material_slot_add()
		mate = context.blend_data.materials.new(ob_names[0])
		context.material_slot.material = mate
		tex_list, col_list, f_list = [], [], []
		
		ob_name = ob_names[0]
		
		base_path = "Assets\\texture\\texture\\"
		
		_MainTex = base_path + ob_name + ".png"
		toonGrayA1 = base_path + r"toon\toonGrayA1.png"
		_ShadowTex = base_path + ob_name + "_shadow.png"
		toonDress_shadow = base_path + r"toon\toonDress_shadow.png"
		
		if False:
			pass
		elif self.type == 'CM3D2/Toony_Lighted_Outline':
			mate['shader1'] = 'CM3D2/Toony_Lighted_Outline'
			mate['shader2'] = 'CM3D2__Toony_Lighted_Outline'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			tex_list.append(("_ToonRamp", "toonGrayA1", toonGrayA1))
			tex_list.append(("_ShadowTex", ob_name + "_shadow", _ShadowTex))
			tex_list.append(("_ShadowRateToon", "toonDress_shadow", toonDress_shadow))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_RimColor", (0.5, 0.5, 0.5, 1)))
			col_list.append(("_OutlineColor", (0, 0, 0, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 0))
			f_list.append(("_OutlineWidth", 0.002))
			f_list.append(("_RimPower", 25))
			f_list.append(("_RimShift", 0))
		elif self.type == 'CM3D2/Toony_Lighted_Trans':
			mate['shader1'] = 'CM3D2/Toony_Lighted_Trans'
			mate['shader2'] = 'CM3D2__Toony_Lighted_Trans'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			tex_list.append(("_ToonRamp", "toonGrayA1", toonGrayA1))
			tex_list.append(("_ShadowTex", ob_name + "_shadow", _ShadowTex))
			tex_list.append(("_ShadowRateToon", "toonDress_shadow", toonDress_shadow))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_RimColor", (0.5, 0.5, 0.5, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 0))
			f_list.append(("_RimPower", 25))
			f_list.append(("_RimShift", 0))
		elif self.type == 'CM3D2/Toony_Lighted_Hair_Outline':
			mate['shader1'] = 'CM3D2/Toony_Lighted_Hair_Outline'
			mate['shader2'] = 'CM3D2__Toony_Lighted_Hair_Outline'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			tex_list.append(("_ToonRamp", "toonGrayA1", toonGrayA1))
			tex_list.append(("_ShadowTex", ob_name + "_shadow", _ShadowTex))
			tex_list.append(("_ShadowRateToon", "toonDress_shadow", toonDress_shadow))
			tex_list.append(("_HiTex", ob_name + "_s", base_path + ob_name + "_s.png"))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_RimColor", (0.5, 0.5, 0.5, 1)))
			col_list.append(("_OutlineColor", (0, 0, 0, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 0))
			f_list.append(("_OutlineWidth", 0.002))
			f_list.append(("_RimPower", 25))
			f_list.append(("_RimShift", 0))
			f_list.append(("_HiRate", 0.5))
			f_list.append(("_HiPow", 0.001))
		elif self.type == 'CM3D2/Mosaic':
			mate['shader1'] = 'CM3D2/Mosaic'
			mate['shader2'] = 'CM3D2__Mosaic'
			tex_list.append(("_RenderTex", ""))
			f_list.append(("_FloatValue1", 30))
		elif self.type == 'Unlit/Texture':
			mate['shader1'] = 'Unlit/Texture'
			mate['shader2'] = 'Unlit__Texture'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			col_list.append(("_Color", (1, 1, 1, 1)))
		elif self.type == 'Unlit/Transparent':
			mate['shader1'] = 'Unlit/Transparent'
			mate['shader2'] = 'Unlit__Transparent'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_RimColor", (0.5, 0.5, 0.5, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 1))
			f_list.append(("_RimPower", 25))
			f_list.append(("_RimShift", 0))
		elif self.type == 'CM3D2/Man':
			mate['shader1'] = 'CM3D2/Man'
			mate['shader2'] = 'CM3D2__Man'
			col_list.append(("_Color", (1, 1, 1, 1)))
			f_list.append(("_FloatValue2", 0.5))
			f_list.append(("_FloatValue3", 1))
		elif self.type == 'Diffuse':
			mate['shader1'] = 'Diffuse'
			mate['shader2'] = 'Diffuse'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			col_list.append(("_Color", (1, 1, 1, 1)))
		elif self.type == 'CM3D2/Toony_Lighted_Trans_NoZ':
			mate['shader1'] = 'CM3D2/Toony_Lighted_Trans_NoZ'
			mate['shader2'] = 'CM3D2__Toony_Lighted_Trans_NoZ'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			tex_list.append(("_ToonRamp", "toonGrayA1", toonGrayA1))
			tex_list.append(("_ShadowTex", ob_name + "_shadow", _ShadowTex))
			tex_list.append(("_ShadowRateToon", "toonDress_shadow", toonDress_shadow))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_RimColor", (0.5, 0.5, 0.5, 1)))
			col_list.append(("_OutlineColor", (0, 0, 0, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 0))
			f_list.append(("_OutlineWidth", 0.002))
			f_list.append(("_RimPower", 25))
			f_list.append(("_RimShift", 0))
		elif self.type == 'CM3D2/Toony_Lighted_Outline_Trans':
			mate['shader1'] = 'CM3D2/Toony_Lighted_Outline_Trans'
			mate['shader2'] = 'CM3D2__Toony_Lighted_Outline_Trans'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			tex_list.append(("_ToonRamp", "toonGrayA1", toonGrayA1))
			tex_list.append(("_ShadowTex", ob_name + "_shadow", _ShadowTex))
			tex_list.append(("_ShadowRateToon", "toonDress_shadow", toonDress_shadow))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_RimColor", (0.5, 0.5, 0.5, 1)))
			col_list.append(("_OutlineColor", (0, 0, 0, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 0))
			f_list.append(("_OutlineWidth", 0.002))
			f_list.append(("_RimPower", 25))
			f_list.append(("_RimShift", 0))
		elif self.type == 'CM3D2/Lighted_Trans':
			mate['shader1'] = 'CM3D2/Lighted_Trans'
			mate['shader2'] = 'CM3D2__Lighted_Trans'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 0))
		elif self.type == 'CM3D2/Toony_Lighted':
			mate['shader1'] = 'CM3D2/Toony_Lighted'
			mate['shader2'] = 'CM3D2__Toony_Lighted'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			tex_list.append(("_ToonRamp", "toonGrayA1", toonGrayA1))
			tex_list.append(("_ShadowTex", ob_name + "_shadow", _ShadowTex))
			tex_list.append(("_ShadowRateToon", "toonDress_shadow", toonDress_shadow))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_RimColor", (0.5, 0.5, 0.5, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 0))
			f_list.append(("_RimPower", 25))
			f_list.append(("_RimShift", 0))
		elif self.type == 'CM3D2/Toony_Lighted_Hair':
			mate['shader1'] = 'CM3D2/Toony_Lighted_Hair_Outline'
			mate['shader2'] = 'CM3D2__Toony_Lighted_Hair_Outline'
			tex_list.append(("_MainTex", ob_name, _MainTex))
			tex_list.append(("_ToonRamp", "toonGrayA1", toonGrayA1))
			tex_list.append(("_ShadowTex", ob_name + "_shadow", _ShadowTex))
			tex_list.append(("_ShadowRateToon", "toonDress_shadow", toonDress_shadow))
			tex_list.append(("_HiTex", ob_name + "_s", base_path + ob_name + "_s.png"))
			col_list.append(("_Color", (1, 1, 1, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			col_list.append(("_RimColor", (0.5, 0.5, 0.5, 1)))
			col_list.append(("_ShadowColor", (0, 0, 0, 1)))
			f_list.append(("_Shininess", 0))
			f_list.append(("_RimPower", 25))
			f_list.append(("_RimShift", 0))
			f_list.append(("_HiRate", 0.5))
			f_list.append(("_HiPow", 0.001))
		
		slot_count = 0
		for data in tex_list:
			slot = mate.texture_slots.create(slot_count)
			tex = context.blend_data.textures.new(data[0], 'IMAGE')
			slot.texture = tex
			if data[1] == "":
				slot_count += 1
				continue
			slot.color = [0, 0, 1]
			img = context.blend_data.images.new(data[1], 128, 128)
			img.filepath = data[2]
			img['cm3d2_path'] = data[2]
			img.source = 'FILE'
			tex.image = img
			slot_count += 1
			
			# tex探し
			if self.is_replace_cm3d2_tex:
				if common.replace_cm3d2_tex(img) and data[0]=='_MainTex':
					me = ob.data
					for face in me.polygons:
						if face.material_index == ob.active_material_index:
							me.uv_textures.active.data[face.index].image = img
		
		for data in col_list:
			slot = mate.texture_slots.create(slot_count)
			mate.use_textures[slot_count] = False
			slot.color = data[1][:3]
			slot.diffuse_color_factor = data[1][3]
			slot.use_rgb_to_intensity = True
			tex = context.blend_data.textures.new(data[0], 'IMAGE')
			slot.texture = tex
			slot_count += 1
		
		for data in f_list:
			slot = mate.texture_slots.create(slot_count)
			mate.use_textures[slot_count] = False
			slot.diffuse_color_factor = data[1]
			tex = context.blend_data.textures.new(data[0], 'IMAGE')
			slot.texture = tex
			slot_count += 1
		
		common.decorate_material(mate, self.is_decorate)
		return {'FINISHED'}

class copy_material(bpy.types.Operator):
	bl_idname = 'material.copy_material'
	bl_label = "マテリアルをクリップボードにコピー"
	bl_description = "表示しているマテリアルをテキスト形式でクリップボードにコピーします"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if 'material' in dir(context):
			mate = context.material
			if mate:
				if 'shader1' in mate.keys() and 'shader2' in mate.keys():
					return True
		return False
	
	def execute(self, context):
		import re, os.path
		
		mate = context.material
		
		output_text = "1000" + "\n"
		output_text = output_text + mate.name.lower() + "\n"
		output_text = output_text + mate.name + "\n"
		output_text = output_text + mate['shader1'] + "\n"
		output_text = output_text + mate['shader2'] + "\n"
		output_text = output_text + "\n"
		
		for tex_slot in mate.texture_slots:
			if not tex_slot:
				continue
			tex = tex_slot.texture
			if tex_slot.use:
				type = 'tex'
			else:
				if tex_slot.use_rgb_to_intensity:
					type = 'col'
				else:
					type = 'f'
			output_text = output_text + type + "\n"
			output_text = output_text + "\t" + common.remove_serial_number(tex.name) + "\n"
			if type == 'tex':
				try:
					img = tex.image
				except:
					self.report(type={'ERROR'}, message="texタイプの設定値の取得に失敗しました、中止します")
					return {'CANCELLED'}
				if img:
					output_text = output_text + '\ttex2d' + "\n"
					output_text = output_text + "\t" + common.remove_serial_number(img.name) + "\n"
					if 'cm3d2_path' in img.keys():
						path = img['cm3d2_path']
					else:
						path = img.filepath
					path = path.replace('\\', '/')
					path = re.sub(r'^[\/\.]*', "", path)
					if not re.search(r'^assets/texture/', path, re.I):
						path = "Assets/texture/texture/" + os.path.basename(path)
					output_text = output_text + "\t" + path + "\n"
					col = tex_slot.color
					output_text = output_text + "\t" + " ".join([str(col[0]), str(col[1]), str(col[2]), str(tex_slot.diffuse_color_factor)]) + "\n"
				else:
					output_text = output_text + "\tnull" + "\n"
			elif type == 'col':
				col = tex_slot.color
				output_text = output_text + "\t" + " ".join([str(col[0]), str(col[1]), str(col[2]), str(tex_slot.diffuse_color_factor)]) + "\n"
			elif type == 'f':
				output_text = output_text + "\t" + str(tex_slot.diffuse_color_factor) + "\n"
		
		context.window_manager.clipboard = output_text
		self.report(type={'INFO'}, message="マテリアルテキストをクリップボードにコピーしました")
		return {'FINISHED'}

class paste_material(bpy.types.Operator):
	bl_idname = 'material.paste_material'
	bl_label = "クリップボードからマテリアルを貼り付け"
	bl_description = "クリップボード内のマテリアル情報から新規マテリアルを作成します"
	bl_options = {'REGISTER', 'UNDO'}
	
	is_decorate = bpy.props.BoolProperty(name="種類に合わせてマテリアルを装飾", default=True)
	
	@classmethod
	def poll(cls, context):
		data = context.window_manager.clipboard
		lines = data.split('\n')
		if len(lines) < 10:
			return False
		match_strs = ['\ntex\n', '\ncol\n', '\nf\n', '\n\t_MainTex\n', '\n\t_Color\n', '\n\t_Shininess\n']
		for s in match_strs:
			if s in data:
				return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'is_decorate')
	
	def execute(self, context):
		data = context.window_manager.clipboard
		lines = data.split('\n')
		
		if not context.material_slot:
			bpy.ops.object.material_slot_add()
		mate = context.blend_data.materials.new(lines[2])
		context.material_slot.material = mate
		
		mate['shader1'] = lines[3]
		mate['shader2'] = lines[4]
		
		slot_index = 0
		line_seek = 5
		for i in range(99999):
			if len(lines) <= line_seek:
				break
			type = common.line_trim(lines[line_seek])
			if not type:
				line_seek += 1
				continue
			if type == 'tex':
				slot = mate.texture_slots.create(slot_index)
				tex = context.blend_data.textures.new(common.line_trim(lines[line_seek+1]), 'IMAGE')
				slot.texture = tex
				sub_type = common.line_trim(lines[line_seek+2])
				line_seek += 3
				if sub_type == 'tex2d':
					img = context.blend_data.images.new(common.line_trim(lines[line_seek]), 128, 128)
					img['cm3d2_path'] = common.line_trim(lines[line_seek+1])
					img.filepath = img['cm3d2_path']
					img.source = 'FILE'
					tex.image = img
					fs = common.line_trim(lines[line_seek+2]).split(' ')
					for fi in range(len(fs)):
						fs[fi] = float(fs[fi])
					slot.color = fs[:3]
					slot.diffuse_color_factor = fs[3]
					line_seek += 3
			
			elif type == 'col':
				slot = mate.texture_slots.create(slot_index)
				tex_name = common.line_trim(lines[line_seek+1])
				tex = context.blend_data.textures.new(tex_name, 'IMAGE')
				mate.use_textures[slot_index] = False
				slot.use_rgb_to_intensity = True
				fs = common.line_trim(lines[line_seek+2]).split(' ')
				for fi in range(len(fs)):
					fs[fi] = float(fs[fi])
				slot.color = fs[:3]
				slot.diffuse_color_factor = fs[3]
				slot.texture = tex
				line_seek += 3
			
			elif type == 'f':
				slot = mate.texture_slots.create(slot_index)
				tex_name = common.line_trim(lines[line_seek+1])
				tex = context.blend_data.textures.new(tex_name, 'IMAGE')
				mate.use_textures[slot_index] = False
				slot.diffuse_color_factor = float(common.line_trim(lines[line_seek+2]))
				slot.texture = tex
				line_seek += 3
			
			else:
				self.report(type={'ERROR'}, message="未知の設定値タイプが見つかりました、中止します")
				return {'CANCELLED'}
			slot_index += 1
		
		common.decorate_material(mate, self.is_decorate)
		self.report(type={'INFO'}, message="クリップボードからマテリアルを貼り付けました")
		return {'FINISHED'}

class decode_cm3d2_bone_names(bpy.types.Operator):
	bl_idname = 'armature.decode_cm3d2_bone_names'
	bl_label = "ボーン名をCM3D2用→Blender用に変換"
	bl_description = "CM3D2で使われてるボーン名をBlenderで左右対称編集できるように変換します"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		import re
		ob = context.active_object
		if ob:
			if ob.type == 'ARMATURE':
				arm = ob.data
				for bone in arm.bones:
					if re.search(r'[_ ]([rRlL])[_ ]', bone.name):
						return True
		return False
	
	def execute(self, context):
		ob = context.active_object
		arm = ob.data
		convert_count = 0
		for bone in arm.bones:
			bone_name = common.decode_bone_name(bone.name)
			if bone_name != bone.name:
				bone.name = bone_name
				convert_count += 1
		if convert_count == 0:
			self.report(type={'WARNING'}, message="変換できる名前が見つかりませんでした")
		else:
			self.report(type={'INFO'}, message="ボーン名をBlender用に変換しました")
		return {'FINISHED'}

class encode_cm3d2_bone_names(bpy.types.Operator):
	bl_idname = 'armature.encode_cm3d2_bone_names'
	bl_label = "ボーン名をBlender用→CM3D2用に変換"
	bl_description = "CM3D2で使われてるボーン名に元に戻します"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		import re
		ob = context.active_object
		if ob:
			if ob.type == 'ARMATURE':
				arm = ob.data
				for bone in arm.bones:
					if bone.name.count('*') == 1:
						if re.search(r'\.([rRlL])$', bone.name):
							return True
		return False
	
	def execute(self, context):
		ob = context.active_object
		arm = ob.data
		convert_count = 0
		for bone in arm.bones:
			bone_name = common.encode_bone_name(bone.name)
			if bone_name != bone.name:
				bone.name = bone_name
				convert_count += 1
		if convert_count == 0:
			self.report(type={'WARNING'}, message="変換できる名前が見つかりませんでした")
		else:
			self.report(type={'INFO'}, message="ボーン名をCM3D2用に戻しました")
		return {'FINISHED'}

class show_text(bpy.types.Operator):
	bl_idname = 'text.show_text'
	bl_label = "テキストを表示"
	bl_description = "指定したテキストをこの領域に表示します"
	bl_options = {'REGISTER', 'UNDO'}
	
	name = bpy.props.StringProperty(name="テキスト名")
	
	@classmethod
	def poll(cls, context):
		if 'text' in dir(context.space_data):
			return True
		return False
	
	def execute(self, context):
		context.space_data.text = bpy.data.texts[self.name]
		return {'FINISHED'}

class copy_text_bone_data(bpy.types.Operator):
	bl_idname = 'text.copy_text_bone_data'
	bl_label = "テキストのボーン情報をコピー"
	bl_description = "テキストのボーン情報をカスタムプロパティへ貼り付ける形にしてクリップボードにコピーします"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if 'BoneData' in context.blend_data.texts.keys():
			if 'LocalBoneData' in context.blend_data.texts.keys():
				return True
		return False
	
	def execute(self, context):
		output_text = ""
		for line in context.blend_data.texts['BoneData'].as_string().split('\n'):
			if not line:
				continue
			output_text = output_text + "BoneData:" + line + "\n"
		for line in context.blend_data.texts['LocalBoneData'].as_string().split('\n'):
			if not line:
				continue
			output_text = output_text + "LocalBoneData:" + line + "\n"
		context.window_manager.clipboard = output_text
		self.report(type={'INFO'}, message="ボーン情報をクリップボードにコピーしました")
		return {'FINISHED'}

class paste_text_bone_data(bpy.types.Operator):
	bl_idname = 'text.paste_text_bone_data'
	bl_label = "テキストのボーン情報を貼り付け"
	bl_description = "クリップボード内のボーン情報をテキストデータに貼り付けます"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		clipboard = context.window_manager.clipboard
		if 'BoneData:' in clipboard and 'LocalBoneData:' in clipboard:
			return True
		return False
	
	def execute(self, context):
		import re
		clipboard = context.window_manager.clipboard
		if "BoneData" in context.blend_data.texts.keys():
			bone_data_text = context.blend_data.texts["BoneData"]
			bone_data_text.clear()
		else:
			bone_data_text = context.blend_data.texts.new("BoneData")
		if "LocalBoneData" in context.blend_data.texts.keys():
			local_bone_data_text = context.blend_data.texts["LocalBoneData"]
			local_bone_data_text.clear()
		else:
			local_bone_data_text = context.blend_data.texts.new("LocalBoneData")
		
		for line in context.window_manager.clipboard.split("\n"):
			r = re.search('^BoneData:(.+)$', line)
			if r:
				if line.count(',') == 4:
					info = r.groups()[0]
					bone_data_text.write(info + "\n")
			r = re.search('^LocalBoneData:(.+)$', line)
			if r:
				if line.count(',') == 1:
					info = r.groups()[0]
					local_bone_data_text.write(info + "\n")
		bone_data_text.current_line_index = 0
		local_bone_data_text.current_line_index = 0
		self.report(type={'INFO'}, message="ボーン情報をクリップボードから貼り付けました")
		return {'FINISHED'}

class remove_all_material_texts(bpy.types.Operator):
	bl_idname = 'text.remove_all_material_texts'
	bl_label = "マテリアル情報テキストを全削除"
	bl_description = "CM3D2で使用できるマテリアルテキストを全て削除します"
	bl_options = {'REGISTER', 'UNDO'}
	
	is_keep_used_material = bpy.props.BoolProperty(name="使用する分は保管", default=True)
	
	@classmethod
	def poll(cls, context):
		if 'Material:0' in context.blend_data.texts.keys():
			return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.prop(self, 'is_keep_used_material')
	
	def execute(self, context):
		remove_texts = []
		pass_count = 0
		for i in range(9999):
			name = 'Material:' + str(i)
			if name in context.blend_data.texts.keys():
				remove_texts.append(context.blend_data.texts[name])
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		if self.is_keep_used_material:
			ob = context.active_object
			if ob:
				remove_texts = remove_texts[len(ob.material_slots):]
		for txt in remove_texts:
			context.blend_data.texts.remove(txt)
		return {'FINISHED'}

class copy_object_bone_data_property(bpy.types.Operator):
	bl_idname = 'object.copy_object_bone_data_property'
	bl_label = "ボーン情報をコピー"
	bl_description = "カスタムプロパティのボーン情報をクリップボードにコピーします"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			if 'BoneData:0' in ob.keys() and 'LocalBoneData:0' in ob.keys():
				return True
		return False
	
	def execute(self, context):
		output_text = ""
		ob = context.active_object
		pass_count = 0
		for i in range(99999):
			name = "BoneData:" + str(i)
			if name in ob.keys():
				output_text = output_text + "BoneData:" + ob[name] + "\n"
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		pass_count = 0
		for i in range(99999):
			name = "LocalBoneData:" + str(i)
			if name in ob.keys():
				output_text = output_text + "LocalBoneData:" + ob[name] + "\n"
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		context.window_manager.clipboard = output_text
		self.report(type={'INFO'}, message="ボーン情報をクリップボードにコピーしました")
		return {'FINISHED'}

class paste_object_bone_data_property(bpy.types.Operator):
	bl_idname = 'object.paste_object_bone_data_property'
	bl_label = "ボーン情報を貼り付け"
	bl_description = "カスタムプロパティのボーン情報をクリップボードから貼り付けます"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			clipboard = context.window_manager.clipboard
			if 'BoneData:' in clipboard and 'LocalBoneData:' in clipboard:
				return True
		return False
	
	def execute(self, context):
		import re
		ob = context.active_object
		pass_count = 0
		for i in range(99999):
			name = "BoneData:" + str(i)
			if name in ob.keys():
				del ob[name]
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		pass_count = 0
		for i in range(99999):
			name = "LocalBoneData:" + str(i)
			if name in ob.keys():
				del ob[name]
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		bone_data_count = 0
		local_bone_data_count = 0
		for line in context.window_manager.clipboard.split("\n"):
			r = re.search('^BoneData:(.+)$', line)
			if r:
				if line.count(',') == 4:
					info = r.groups()[0]
					name = "BoneData:" + str(bone_data_count)
					ob[name] = info
					bone_data_count += 1
			r = re.search('^LocalBoneData:(.+)$', line)
			if r:
				if line.count(',') == 1:
					info = r.groups()[0]
					name = "LocalBoneData:" + str(local_bone_data_count)
					ob[name] = info
					local_bone_data_count += 1
		self.report(type={'INFO'}, message="ボーン情報をクリップボードから貼り付けました")
		return {'FINISHED'}

class remove_object_bone_data_property(bpy.types.Operator):
	bl_idname = 'object.remove_object_bone_data_property'
	bl_label = "ボーン情報を削除"
	bl_description = "カスタムプロパティのボーン情報を全て削除します"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			if 'BoneData:0' in ob.keys() and 'LocalBoneData:0' in ob.keys():
				return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.label(text="カスタムプロパティのボーン情報を全て削除します", icon='CANCEL')
	
	def execute(self, context):
		ob = context.active_object
		pass_count = 0
		for i in range(99999):
			name = "BoneData:" + str(i)
			if name in ob.keys():
				del ob[name]
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		pass_count = 0
		for i in range(99999):
			name = "LocalBoneData:" + str(i)
			if name in ob.keys():
				del ob[name]
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		self.report(type={'INFO'}, message="ボーン情報を削除しました")
		return {'FINISHED'}

class copy_armature_bone_data_property(bpy.types.Operator):
	bl_idname = 'object.copy_armature_bone_data_property'
	bl_label = "ボーン情報をコピー"
	bl_description = "カスタムプロパティのボーン情報をクリップボードにコピーします"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			if ob.type == 'ARMATURE':
				arm = ob.data
				if 'BoneData:0' in arm.keys() and 'LocalBoneData:0' in arm.keys():
					return True
		return False
	
	def execute(self, context):
		output_text = ""
		ob = context.active_object.data
		pass_count = 0
		for i in range(99999):
			name = "BoneData:" + str(i)
			if name in ob.keys():
				output_text = output_text + "BoneData:" + ob[name] + "\n"
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		pass_count = 0
		for i in range(99999):
			name = "LocalBoneData:" + str(i)
			if name in ob.keys():
				output_text = output_text + "LocalBoneData:" + ob[name] + "\n"
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		context.window_manager.clipboard = output_text
		self.report(type={'INFO'}, message="ボーン情報をクリップボードにコピーしました")
		return {'FINISHED'}

class paste_armature_bone_data_property(bpy.types.Operator):
	bl_idname = 'object.paste_armature_bone_data_property'
	bl_label = "ボーン情報を貼り付け"
	bl_description = "カスタムプロパティのボーン情報をクリップボードから貼り付けます"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			if ob.type == 'ARMATURE':
				clipboard = context.window_manager.clipboard
				if 'BoneData:' in clipboard and 'LocalBoneData:' in clipboard:
					return True
		return False
	
	def execute(self, context):
		import re
		ob = context.active_object.data
		pass_count = 0
		for i in range(99999):
			name = "BoneData:" + str(i)
			if name in ob.keys():
				del ob[name]
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		pass_count = 0
		for i in range(99999):
			name = "LocalBoneData:" + str(i)
			if name in ob.keys():
				del ob[name]
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		bone_data_count = 0
		local_bone_data_count = 0
		for line in context.window_manager.clipboard.split("\n"):
			r = re.search('^BoneData:(.+)$', line)
			if r:
				if line.count(',') == 4:
					info = r.groups()[0]
					name = "BoneData:" + str(bone_data_count)
					ob[name] = info
					bone_data_count += 1
			r = re.search('^LocalBoneData:(.+)$', line)
			if r:
				if line.count(',') == 1:
					info = r.groups()[0]
					name = "LocalBoneData:" + str(local_bone_data_count)
					ob[name] = info
					local_bone_data_count += 1
		self.report(type={'INFO'}, message="ボーン情報をクリップボードから貼り付けました")
		return {'FINISHED'}

class remove_armature_bone_data_property(bpy.types.Operator):
	bl_idname = 'object.remove_armature_bone_data_property'
	bl_label = "ボーン情報を削除"
	bl_description = "カスタムプロパティのボーン情報を全て削除します"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		ob = context.active_object
		if ob:
			if ob.type == 'ARMATURE':
				arm = ob.data
				if 'BoneData:0' in arm.keys() and 'LocalBoneData:0' in arm.keys():
					return True
		return False
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.label(text="カスタムプロパティのボーン情報を全て削除します", icon='CANCEL')
	
	def execute(self, context):
		ob = context.active_object.data
		pass_count = 0
		for i in range(99999):
			name = "BoneData:" + str(i)
			if name in ob.keys():
				del ob[name]
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		pass_count = 0
		for i in range(99999):
			name = "LocalBoneData:" + str(i)
			if name in ob.keys():
				del ob[name]
			else:
				pass_count += 1
			if 10 < pass_count:
				break
		self.report(type={'INFO'}, message="ボーン情報を削除しました")
		return {'FINISHED'}

class show_image(bpy.types.Operator):
	bl_idname = 'image.show_image'
	bl_label = "画像を表示"
	bl_description = "指定の画像をUV/画像エディターに表示します"
	bl_options = {'REGISTER', 'UNDO'}
	
	image_name = bpy.props.StringProperty(name="画像名")
	
	def execute(self, context):
		if self.image_name in context.blend_data.images.keys():
			img = context.blend_data.images[self.image_name]
		else:
			self.report(type={'ERROR'}, message="指定された画像が見つかりません")
			return {'CANCELLED'}
		
		area = common.get_request_area(context, 'IMAGE_EDITOR')
		if area:
			for space in area.spaces:
				if space.type == 'IMAGE_EDITOR':
					space.image = img
		else:
			self.report(type={'ERROR'}, message="画像を表示できるエリアが見つかりませんでした")
			return {'CANCELLED'}
		return {'FINISHED'}

class show_cm3d2_converter_preference(bpy.types.Operator):
	bl_idname = 'wm.show_cm3d2_converter_preference'
	bl_label = "CM3D2 Converterの設定画面を開く"
	bl_description = "CM3D2 Converterアドオンの設定画面を表示します"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		import addon_utils
		my_info = None
		for module in addon_utils.modules():
			info = addon_utils.module_bl_info(module)
			if info['name'] == "CM3D2 Converter":
				my_info = info
				break
		area = common.get_request_area(context, 'USER_PREFERENCES')
		if area and my_info:
			context.user_preferences.active_section = 'ADDONS'
			context.window_manager.addon_search = my_info['name']
			context.window_manager.addon_filter = 'All'
			if 'COMMUNITY' not in context.window_manager.addon_support:
				context.window_manager.addon_support = {'OFFICIAL', 'COMMUNITY'}
			if not my_info['show_expanded']:
				bpy.ops.wm.addon_expand(module=my_info['name'])
		else:
			self.report(type={'ERROR'}, message="表示できるエリアが見つかりませんでした")
			return {'CANCELLED'}
		return {'FINISHED'}

class sync_tex_color_ramps(bpy.types.Operator):
	bl_idname = 'texture.sync_tex_color_ramps'
	bl_label = "設定をテクスチャの色に同期"
	bl_description = "この設定値をテクスチャの色に適用してわかりやすくします"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if 'texture_slot' in dir(context):
			if context.texture_slot:
				if 'texture' in dir(context):
					if context.texture:
						return True
		return False
	
	def execute(self, context):
		for mate in context.blend_data.materials:
			if 'shader1' in mate.keys() and 'shader2' in mate.keys():
				for slot in mate.texture_slots:
					if not slot:
						continue
					common.set_texture_color(slot)
		return {'FINISHED'}

class replace_cm3d2_tex(bpy.types.Operator):
	bl_idname = 'image.replace_cm3d2_tex'
	bl_label = "テクスチャを探す"
	bl_description = "CM3D2本体のインストールフォルダからtexファイルを探して開きます"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if 'texture' in dir(context):
			tex = context.texture
			if 'image' in dir(tex):
				return True
		return False
	
	def execute(self, context):
		tex = context.texture
		img = tex.image
		if not common.replace_cm3d2_tex(img):
			self.report(type={'ERROR'}, message="見つかりませんでした")
			return {'CANCELLED'}
		return {'FINISHED'}

class sync_object_transform(bpy.types.Operator):
	bl_idname = 'object.sync_object_transform'
	bl_label = "オブジェクトの位置を合わせる"
	bl_description = "アクティブオブジェクトの中心位置を、他の選択オブジェクトの中心位置に合わせます"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		obs = context.selected_objects
		if len(obs) != 2:
			return False
		for ob in obs:
			if ob.type != 'MESH':
				return False
		return True
	
	def execute(self, context):
		target_ob = context.active_object
		for ob in context.selected_objects:
			if target_ob.name != ob.name:
				source_ob = ob
				break
		
		for area in context.screen.areas:
			if area.type == 'VIEW_3D':
				for space in area.spaces:
					if space.type == 'VIEW_3D':
						target_space = space
						break
		
		pre_cursor_location = target_space.cursor_location[:]
		target_space.cursor_location = source_ob.location[:]
		
		source_ob.select = False
		bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
		source_ob.select = True
		
		target_space.cursor_location = pre_cursor_location[:]
		return {'FINISHED'}
