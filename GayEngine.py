import math
import time
import random
import tkinter as tk
from tkinter import ttk, Canvas, Frame, Label, Button, Scale, HORIZONTAL, Entry, filedialog, messagebox
import json
import os
import sys
import subprocess
import tempfile
import shutil
import re

class ZBuffer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.buffer = [[float('-inf') for _ in range(height)] for _ in range(width)]
    
    def clear(self):
        self.buffer = [[float('-inf') for _ in range(self.height)] for _ in range(self.width)]
    
    def test_and_set(self, x, y, z):
        x = int(x)
        y = int(y)
        if 0 <= x < self.width and 0 <= y < self.height:
            if z > self.buffer[x][y]:
                self.buffer[x][y] = z
                return True
        return False

class Texture:
    def __init__(self, width, height, color="#FFFFFF"):
        self.width = width
        self.height = height
        self.pixels = [[color for _ in range(height)] for _ in range(width)]
    
    def set_pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[x][y] = color
    
    def get_pixel(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.pixels[x][y]
        return "#000000"
    
    def create_checkerboard(self, color1="#444444", color2="#666666", size=32):
        for x in range(self.width):
            for y in range(self.height):
                if ((x // size) + (y // size)) % 2 == 0:
                    self.pixels[x][y] = color1
                else:
                    self.pixels[x][y] = color2

class TextureManager:
    def __init__(self):
        self.textures = {}
        self.create_default_textures()
    
    def create_default_textures(self):
        cube_tex = Texture(32, 32)
        for x in range(32):
            for y in range(32):
                if x < 2 or x > 29 or y < 2 or y > 29:
                    cube_tex.set_pixel(x, y, "#000000")
                elif (x + y) % 8 < 4:
                    cube_tex.set_pixel(x, y, "#CCCCCC")
                else:
                    cube_tex.set_pixel(x, y, "#AAAAAA")
        self.textures["cube"] = cube_tex

class Vector3:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z
    
    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
    
    def normalize(self):
        length = self.length()
        if length > 0:
            return Vector3(self.x / length, self.y / length, self.z / length)
        return Vector3()
    
    def rotate_x(self, angle):
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        y = self.y * cos_a - self.z * sin_a
        z = self.y * sin_a + self.z * cos_a
        return Vector3(self.x, y, z)
    
    def rotate_y(self, angle):
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        x = self.x * cos_a + self.z * sin_a
        z = -self.x * sin_a + self.z * cos_a
        return Vector3(x, self.y, z)
    
    def rotate_z(self, angle):
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        x = self.x * cos_a - self.y * sin_a
        y = self.x * sin_a + self.y * cos_a
        return Vector3(x, y, self.z)
    
    def to_dict(self):
        return {"x": self.x, "y": self.y, "z": self.z}
    
    @staticmethod
    def from_dict(data):
        return Vector3(data["x"], data["y"], data["z"])
    
    def __str__(self):
        return f"({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"

class Transform:
    def __init__(self):
        self.position = Vector3()
        self.rotation = Vector3()
        self.scale = Vector3(1, 1, 1)
    
    def to_dict(self):
        return {
            "position": self.position.to_dict(),
            "rotation": self.rotation.to_dict(),
            "scale": self.scale.to_dict()
        }
    
    @staticmethod
    def from_dict(data):
        transform = Transform()
        transform.position = Vector3.from_dict(data["position"])
        transform.rotation = Vector3.from_dict(data["rotation"])
        transform.scale = Vector3.from_dict(data["scale"])
        return transform

class CollisionBox:
    def __init__(self, min_point, max_point):
        self.min = min_point
        self.max = max_point
    
    def intersects(self, other):
        return (self.min.x <= other.max.x and self.max.x >= other.min.x and
                self.min.y <= other.max.y and self.max.y >= other.min.y and
                self.min.z <= other.max.z and self.max.z >= other.min.z)
    
    def get_transformed(self, transform):
        half_size = Vector3(
            abs(self.max.x - self.min.x) * 0.5 * transform.scale.x,
            abs(self.max.y - self.min.y) * 0.5 * transform.scale.y,
            abs(self.max.z - self.min.z) * 0.5 * transform.scale.z
        )
        
        center = Vector3(
            transform.position.x,
            transform.position.y,
            transform.position.z
        )
        
        return CollisionBox(
            Vector3(center.x - half_size.x, center.y - half_size.y, center.z - half_size.z),
            Vector3(center.x + half_size.x, center.y + half_size.y, center.z + half_size.z)
        )

class Player:
    def __init__(self):
        self.name = "Player"
        self.transform = Transform()
        self.velocity = Vector3()
        self.on_ground = False
        self.move_speed = 1.3
        self.jump_force = 2.3
        self.rotation_speed = 5.0
        self.camera_height = 1.7
        self.collision_enabled = True
        self.collision_box = CollisionBox(Vector3(-0.4, 0, -0.4), Vector3(0.4, 2.0, 0.4))
        self.is_player = True
        self.spin_speed = 2.0
        # Добавляем ссылку на визуальный объект
        self.visual_object = None
    
    def update(self, pressed_keys, collidable_objects):
        # Поворот камеры
        if 'left' in pressed_keys:
            self.transform.rotation.y -= self.rotation_speed
        if 'right' in pressed_keys:
            self.transform.rotation.y += self.rotation_speed
    
        # Движение (поддерживаем и стрелки и WASD)
        direction = Vector3()
        if 'w' in pressed_keys or 'up' in pressed_keys:
            direction.z -= 1
        if 's' in pressed_keys or 'down' in pressed_keys:
            direction.z += 1
        if 'a' in pressed_keys:
            direction.x -= 1
        if 'd' in pressed_keys:
            direction.x += 1
    
        if direction.length() > 0:
            direction = direction.normalize()
            direction = direction.rotate_y(self.transform.rotation.y)
        
            # Двигаемся только если нет коллизии
            new_position = self.transform.position + direction * (self.move_speed * 0.1)
            if not self.check_collision(new_position, collidable_objects):
                self.transform.position = new_position
    
        # Прыжок
        if 'space' in pressed_keys and self.on_ground:
            self.velocity.y = self.jump_force * 0.1
            self.on_ground = False
    
        # Гравитация
        if not self.on_ground:
            self.velocity.y -= 0.015
            new_position = Vector3(
                self.transform.position.x,
                self.transform.position.y + self.velocity.y,
                self.transform.position.z
            )
        
            if not self.check_collision(new_position, collidable_objects):
                self.transform.position = new_position
            else:
                if self.velocity.y < 0:  # Падение вниз
                    self.on_ground = True
                self.velocity.y = 0
    
        # Проверяем, не упали ли мы ниже минимальной высоты
        if self.transform.position.y < -10:
            self.transform.position = Vector3(0, 10, 0)
            self.velocity = Vector3()
            self.on_ground = False
        
        # ОБНОВЛЯЕМ ПОЗИЦИЮ ВИЗУАЛЬНОГО ОБЪЕКТА ИГРОКА
        if self.visual_object:
            self.visual_object.transform.position = self.transform.position
            self.visual_object.transform.rotation = self.transform.rotation

    def check_collision(self, new_position, collidable_objects):
        if not self.collision_enabled:
            return False

        temp_transform = Transform()
        temp_transform.position = new_position
        temp_transform.scale = self.transform.scale
    
        player_box = self.collision_box.get_transformed(temp_transform)
    
        for obj in collidable_objects:
            if (hasattr(obj, 'collision_enabled') and 
                obj.collision_enabled and 
                not getattr(obj, 'is_player', False)):
                obj_box = obj.collision_box.get_transformed(obj.transform)
                if player_box.intersects(obj_box):
                    return True

        return False
    
    def get_camera_position(self):
        return Vector3(
            self.transform.position.x,
            self.transform.position.y + self.camera_height,
            self.transform.position.z
        )
    
    def get_camera_rotation(self):
        return Vector3(0, self.transform.rotation.y, 0)

class GameObject:
    def __init__(self, name, shape="cube"):
        self.name = name
        self.shape = shape
        self.transform = Transform()
        self.color = f"#{random.randint(50, 200):02x}{random.randint(50, 200):02x}{random.randint(50, 200):02x}"
        self.selected = False
        self.is_player = False
        self.collision_enabled = True
        
        # Создаем коллизию в зависимости от формы объекта
        if shape == "cube":
            self.collision_box = CollisionBox(Vector3(-0.5, -0.5, -0.5), Vector3(0.5, 0.5, 0.5))
        elif shape == "sphere":
            self.collision_box = CollisionBox(Vector3(-0.5, -0.5, -0.5), Vector3(0.5, 0.5, 0.5))
        else:
            self.collision_box = CollisionBox(Vector3(-0.5, -0.5, -0.5), Vector3(0.5, 0.5, 0.5))
    
    def to_dict(self):
        return {
            "name": self.name,
            "shape": self.shape,
            "transform": self.transform.to_dict(),
            "color": self.color,
            "is_player": self.is_player,
            "collision_enabled": self.collision_enabled
        }
    
    @staticmethod
    def from_dict(data):
        obj = GameObject(data["name"], data["shape"])
        obj.transform = Transform.from_dict(data["transform"])
        obj.color = data["color"]
        obj.is_player = data["is_player"]
        obj.collision_enabled = data.get("collision_enabled", True)
        return obj

class GayScriptInterpreter:
    def __init__(self, engine):
        self.engine = engine
        self.scripts = []
        self.variables = {}
        self.current_object = None
        self.line_fields = {}
    
    def load_script(self, script_content, script_name="Script"):
        try:
            script_data = {
                'name': script_name,
                'content': script_content,
                'lines': [],
                'target_objects': [],
                'inspector_fields': {},
                'parsed': False,
                'line_definitions': {},
                'initial_values': {},
                'using_objects': {}
            }
            
            lines = script_content.split('\n')
            current_section = None
            in_if_block = False
            current_if = None
            if_stack = []
            
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line == "GameScript":
                    current_section = "header"
                    continue
                
                if line.startswith("Working"):
                    if current_section == "header" or current_section == "body":
                        target_path = line.replace("Working", "").strip()
                        script_data['target_objects'].append(target_path)
                        current_section = "body"
                    continue
                
                if line.startswith("using"):
                    parts = line.split(':')
                    if len(parts) >= 1:
                        obj_name = parts[0].replace("using", "").strip()
                        script_data['using_objects'][obj_name] = obj_name
                    continue
                
                if line == "{":
                    continue
                
                if line == "}":
                    if if_stack:
                        if_stack.pop()
                    if not if_stack:
                        in_if_block = False
                        current_if = None
                    continue
                
                if current_section == "body":
                    self.parse_script_line(line, script_data, if_stack, in_if_block, current_if)
            
            script_data['parsed'] = True
            self.scripts.append(script_data)
            self.engine.log(f"GayScript loaded: {script_name}")
            return True
            
        except Exception as e:
            self.engine.log(f"GayScript parse error: {str(e)}")
            return False

    def parse_script_line(self, line, script_data, if_stack, in_if_block, current_if):
        line = line.strip()
        
        # Обработка условий if
        if line.startswith('if '):
            condition = line.replace('if ', '').strip()
            if_data = {
                'type': 'if_condition',
                'condition': condition,
                'then_branch': [],
                'else_branch': [],
                'in_else': False
            }
            
            if if_stack:
                # Вложенное условие
                parent_if = if_stack[-1]
                if parent_if['in_else']:
                    parent_if['else_branch'].append(if_data)
                else:
                    parent_if['then_branch'].append(if_data)
            else:
                script_data['lines'].append(if_data)
            
            if_stack.append(if_data)
            return
        
        # Обработка else
        if line == 'else':
            if if_stack:
                if_stack[-1]['in_else'] = True
            return
        
        # Обработка line полей
        if line.startswith('line "'):
            match = re.match(r'line "([^"]+)"', line)
            if match:
                field_label = match.group(1)
                field_id = f"line_{len(script_data['line_definitions']) + 1}"
                script_data['line_definitions'][field_id] = {
                    'label': field_label,
                    'value': '',
                    'type': 'input_field',
                    'initial_value': ''
                }
                if "Speed" in field_label:
                    script_data['line_definitions'][field_id]['initial_value'] = "5"
                elif "Jump" in field_label:
                    script_data['line_definitions'][field_id]['initial_value'] = "10"
                elif "Rotation" in field_label:
                    script_data['line_definitions'][field_id]['initial_value'] = "2"
                self.engine.log(f"GayScript: Defined field '{field_label}' as {field_id}")
        
        # Обработка line.ask
        elif line.startswith('line.ask'):
            parts = line.split()
            if len(parts) >= 2:
                property_path = parts[1]
                if script_data['line_definitions']:
                    last_field_id = list(script_data['line_definitions'].keys())[-1]
                    script_data['line_definitions'][last_field_id]['target_property'] = property_path
                    self.engine.log(f"GayScript: Bound {last_field_id} to {property_path}")
        
        # Обработка присваивания с [line]
        elif '= [line]' in line:
            left_side = line.split('=')[0].strip()
            if script_data['line_definitions']:
                last_field_id = list(script_data['line_definitions'].keys())[-1]
                line_data = {
                    'type': 'assignment',
                    'property': left_side,
                    'source': last_field_id,
                    'original_line': line
                }
                
                if if_stack:
                    parent_if = if_stack[-1]
                    if parent_if['in_else']:
                        parent_if['else_branch'].append(line_data)
                    else:
                        parent_if['then_branch'].append(line_data)
                else:
                    script_data['lines'].append(line_data)
        
        # Обработка прямого присваивания
        elif '=' in line and '[line]' not in line:
            left, right = line.split('=', 1)
            left = left.strip()
            right = right.strip()
            
            if script_data['line_definitions']:
                last_field_id = list(script_data['line_definitions'].keys())[-1]
                if right.strip():
                    script_data['line_definitions'][last_field_id]['initial_value'] = right
            
            line_data = {
                'type': 'direct_assignment', 
                'property': left,
                'value': right,
                'original_line': line
            }
            
            if if_stack:
                parent_if = if_stack[-1]
                if parent_if['in_else']:
                    parent_if['else_branch'].append(line_data)
                else:
                    parent_if['then_branch'].append(line_data)
            else:
                script_data['lines'].append(line_data)
        
        # Обработка других команд
        else:
            line_data = {
                'type': 'command',
                'command': line,
                'original_line': line
            }
            
            if if_stack:
                parent_if = if_stack[-1]
                if parent_if['in_else']:
                    parent_if['else_branch'].append(line_data)
                else:
                    parent_if['then_branch'].append(line_data)
            else:
                script_data['lines'].append(line_data)

    def find_object_by_path(self, path):
        if not path:
            return None
        clean_path = path.replace("Hierarchy.", "")
    
        # Если ищем игрока - возвращаем физического игрока из движка
        if clean_path == "Player" and self.engine.player:
            return self.engine.player
    
        # Ищем обычные объекты
        for obj in self.engine.objects:
            if obj.name == clean_path:
                return obj
        return None

    def set_object_property(self, obj, property_path, value):
        try:
            parts = property_path.split('.')
            if len(parts) == 2:
                obj_name, prop_name = parts
                
                # Проверяем using объекты
                if obj_name in self.current_script.get('using_objects', {}):
                    target_obj = self.find_object_by_path(f"Hierarchy.{obj_name}")
                    if target_obj:
                        obj = target_obj
                
                if obj_name != "Player" and obj_name != "Block" and obj_name != obj.name:
                    return
                
                if obj_name == "Player" and hasattr(obj, 'is_player') and obj.is_player and self.engine.player:
                    self.set_player_property(prop_name, value)
                else:
                    self.set_gameobject_property(obj, prop_name, value)
            
        except Exception as e:
            self.engine.log(f"GayScript property error: {str(e)}")

    def set_player_property(self, prop_name, value):
        player = self.engine.player
        if not player:
            return
        
        parsed_value = self.parse_value(value)
        
        if prop_name == "Speed":
            player.move_speed = float(parsed_value)
            self.engine.log(f"GayScript: Set Player.Speed = {parsed_value}")
        elif prop_name == "JumpForce":
            player.jump_force = float(parsed_value)
            self.engine.log(f"GayScript: Set Player.JumpForce = {parsed_value}")
        elif prop_name == "Colision":
            player.collision_enabled = bool(parsed_value)
            self.engine.log(f"GayScript: Set Player.Colision = {parsed_value}")
        elif prop_name == "CameraRotationSpeed":
            player.rotation_speed = float(parsed_value)
            self.engine.log(f"GayScript: Set Player.CameraRotationSpeed = {parsed_value}")
        elif prop_name == "SpinSpeed":
            player.spin_speed = float(parsed_value)
            self.engine.log(f"GayScript: Set Player.SpinSpeed = {parsed_value}")

    def set_gameobject_property(self, obj, prop_name, value):
        parsed_value = self.parse_value(value)
        
        if prop_name == "Position":
            if isinstance(parsed_value, (list, tuple)) and len(parsed_value) == 3:
                obj.transform.position = Vector3(float(parsed_value[0]), float(parsed_value[1]), float(parsed_value[2]))
                self.engine.log(f"GayScript: Set {obj.name}.Position = {parsed_value}")
        elif prop_name == "Rotation":
            if isinstance(parsed_value, (list, tuple)) and len(parsed_value) == 3:
                obj.transform.rotation = Vector3(float(parsed_value[0]), float(parsed_value[1]), float(parsed_value[2]))
                self.engine.log(f"GayScript: Set {obj.name}.Rotation = {parsed_value}")
        elif prop_name == "Scale":
            if isinstance(parsed_value, (list, tuple)) and len(parsed_value) == 3:
                obj.transform.scale = Vector3(float(parsed_value[0]), float(parsed_value[1]), float(parsed_value[2]))
                self.engine.log(f"GayScript: Set {obj.name}.Scale = {parsed_value}")
        elif prop_name == "Color":
            if isinstance(parsed_value, (list, tuple)) and len(parsed_value) == 3:
                r, g, b = int(parsed_value[0]), int(parsed_value[1]), int(parsed_value[2])
                obj.color = f"#{r:02x}{g:02x}{b:02x}"
                self.engine.log(f"GayScript: Set {obj.name}.Color = ({r}, {g}, {b})")
        elif prop_name == "Colision":
            obj.collision_enabled = bool(parsed_value)
            self.engine.log(f"GayScript: Set {obj.name}.Colision = {parsed_value}")

    def parse_value(self, value_str):
        value_str = str(value_str).strip()
        if ',' in value_str:
            return [x.strip() for x in value_str.split(',')]
        try:
            if value_str.lower() == 'true':
                return True
            elif value_str.lower() == 'false':
                return False
            return float(value_str)
        except ValueError:
            return value_str

    def evaluate_condition(self, condition):
        try:
            if 'Colision ==' in condition:
                # ИСПРАВЛЕНИЕ: правильное разбиение условия
                # Убираем все точки из левой части до сравнения
                parts = condition.split(' Colision == ')
                if len(parts) == 2:
                    obj1_name = parts[0].strip()
                    obj2_name = parts[1].strip()
                
                    # УБИРАЕМ ТОЧКУ И ВСЕ ПОСЛЕ НЕЕ ИЗ ЛЕВОЙ ЧАСТИ
                    if '.' in obj1_name:
                        obj1_name = obj1_name.split('.')[0].strip()
                
                    self.engine.log(f"DEBUG: Checking collision between '{obj1_name}' and '{obj2_name}'")
                
                    obj1 = self.find_object_by_path(f"Hierarchy.{obj1_name}")
                    obj2 = self.find_object_by_path(f"Hierarchy.{obj2_name}")
                
                    self.engine.log(f"DEBUG: obj1 found: {obj1 is not None}, obj2 found: {obj2 is not None}")
                
                    if obj1:
                        self.engine.log(f"DEBUG: {obj1_name}.collision_enabled = {getattr(obj1, 'collision_enabled', 'NO ATTR')}")
                    if obj2:
                        self.engine.log(f"DEBUG: {obj2_name}.collision_enabled = {getattr(obj2, 'collision_enabled', 'NO ATTR')}")
            
                # ВАЖНО: проверяем, что коллизия ВКЛЮЧЕНА у обоих объектов
                    if (obj1 and obj2 and 
                        hasattr(obj1, 'collision_enabled') and obj1.collision_enabled and
                        hasattr(obj2, 'collision_enabled') and obj2.collision_enabled):
                    
                        self.engine.log(f"DEBUG: Both objects have collision enabled")
                    
                        # Проверяем факт столкновения
                        if hasattr(obj1, 'collision_box') and hasattr(obj2, 'collision_box'):
                            obj1_box = obj1.collision_box.get_transformed(obj1.transform)
                            obj2_box = obj2.collision_box.get_transformed(obj2.transform)
                            result = obj1_box.intersects(obj2_box)
                            self.engine.log(f"DEBUG: Bounding box intersection = {result}")
                            self.engine.log(f"GayScript: Collision check {obj1_name} vs {obj2_name} = {result}")
                            return result
                        else:
                            self.engine.log(f"DEBUG: Missing collision_box attribute")
                    else:
                        self.engine.log(f"DEBUG: Collision not enabled for both objects")
        
            return False
        except Exception as e:
            self.engine.log(f"Condition evaluation error: {str(e)}")
            return False

    def execute_script(self, script_data, apply_initial_values=False):
        if not script_data['parsed']:
            return
        
        try:
            self.current_script = script_data
            
            target_objects = []
            for target_path in script_data['target_objects']:
                target_obj = self.find_object_by_path(target_path)
                if target_obj:
                    target_objects.append(target_obj)
            
            if not target_objects:
                self.engine.log(f"GayScript: No objects found for: {script_data['target_objects']}")
                return
            
            if apply_initial_values:
                for field_id, field_data in script_data['line_definitions'].items():
                    if field_data.get('initial_value'):
                        field_data['value'] = field_data['initial_value']
                        self.engine.log(f"GayScript: Applied initial value '{field_data['initial_value']}' to {field_id}")
            
            # Выполняем для всех целевых объектов
            for target_obj in target_objects:
                self.execute_lines(script_data['lines'], target_obj)
                    
        except Exception as e:
            self.engine.log(f"GayScript execution error: {str(e)}")

    def execute_lines(self, lines, target_obj):
        for line_data in lines:
            if line_data['type'] == 'if_condition':
                condition_result = self.evaluate_condition(line_data['condition'])
                if condition_result:
                    self.execute_lines(line_data['then_branch'], target_obj)
                else:
                    self.execute_lines(line_data['else_branch'], target_obj)
            else:
                self.execute_line(line_data, target_obj)

    def execute_line(self, line_data, target_obj):
        if line_data['type'] == 'assignment':
            field_value = self.current_script['line_definitions'].get(line_data['source'], {}).get('value', '')
            if field_value:
                self.set_object_property(target_obj, line_data['property'], field_value)
        
        elif line_data['type'] == 'direct_assignment':
            self.set_object_property(target_obj, line_data['property'], line_data['value'])
        
        elif line_data['type'] == 'command':
            if '=' in line_data['command']:
                left, right = line_data['command'].split('=', 1)
                self.set_object_property(target_obj, left.strip(), right.strip())

    def update_line_field(self, script_data, field_id, value):
        if field_id in script_data['line_definitions']:
            script_data['line_definitions'][field_id]['value'] = value
            self.engine.log(f"GayScript: Field {field_id} updated to '{value}'")
            
            if self.engine.game_mode:
                for target_path in script_data['target_objects']:
                    target_obj = self.find_object_by_path(target_path)
                    if target_obj and script_data['line_definitions'][field_id].get('target_property'):
                        self.set_object_property(target_obj, 
                                              script_data['line_definitions'][field_id]['target_property'], 
                                              value)

    def execute_all_scripts(self, apply_initial_values=False):
        for script in self.scripts:
            self.execute_script(script, apply_initial_values)

    def update_scripts(self):
        """Постоянное обновление скриптов в игровом режиме"""
        if not self.engine.game_mode:
            return
        
        for script in self.scripts:
            if script['parsed']:
                try:
                    # ВАЖНО: выполняем скрипт каждый кадр для постоянной проверки условий
                    self.execute_script(script)
                except Exception as e:
                    self.engine.log(f"Script update error: {str(e)}")

class SceneSerializer:
    @staticmethod
    def serialize_scene(engine):
        scene_data = {
            "metadata": {
                "version": "1.1",
                "engine": "GayEngine",
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "object_count": len(engine.objects)
            },
            "camera": {
                "position": engine.scene_camera.position.to_dict(),
                "rotation": engine.scene_camera.rotation.to_dict()
            },
            "objects": [obj.to_dict() for obj in engine.objects],
            "gayscripts": []
        }
        
        for script in engine.script_interpreter.scripts:
            script_data = {
                'name': script['name'],
                'content': script['content'],
                'target_objects': script['target_objects'],
                'line_values': {},
                'using_objects': script.get('using_objects', {})
            }
            
            for field_id, field_data in script['line_definitions'].items():
                script_data['line_values'][field_id] = {
                    'value': field_data['value'],
                    'initial_value': field_data.get('initial_value', '')
                }
            
            scene_data['gayscripts'].append(script_data)
            
        return scene_data
    
    @staticmethod
    def deserialize_scene(engine, scene_data):
        engine.objects = []
        engine.object_list.delete(0, tk.END)
        engine.selected_object = None
        engine.player = None
        
        if "camera" in scene_data:
            engine.scene_camera.position = Vector3.from_dict(scene_data["camera"]["position"])
            engine.scene_camera.rotation = Vector3.from_dict(scene_data["camera"]["rotation"])
        
        if "objects" in scene_data:
            for obj_data in scene_data["objects"]:
                obj = GameObject.from_dict(obj_data)
                engine.objects.append(obj)
                engine.object_list.insert(tk.END, obj.name)
                
                if obj.is_player:
                    engine.player = Player()
                    engine.player.transform.position = obj.transform.position
                    engine.player.visual_object = obj
        
        if 'gayscripts' in scene_data:
            engine.script_interpreter.scripts = []
            for script_data in scene_data['gayscripts']:
                if engine.script_interpreter.load_script(script_data['content'], script_data['name']):
                    loaded_script = engine.script_interpreter.scripts[-1]
                    if 'line_values' in script_data:
                        for field_id, field_values in script_data['line_values'].items():
                            if field_id in loaded_script['line_definitions']:
                                loaded_script['line_definitions'][field_id]['value'] = field_values['value']
                                loaded_script['line_definitions'][field_id]['initial_value'] = field_values.get('initial_value', '')
                    if 'using_objects' in script_data:
                        loaded_script['using_objects'] = script_data['using_objects']
            
            engine.log(f"Loaded {len(scene_data['gayscripts'])} GayScripts with saved values")
        
        engine.log(f"Scene loaded: {len(engine.objects)} objects")
        if engine.player:
            engine.log("Player object found in scene")

class GameBuilder:
    def __init__(self, engine):
        self.engine = engine
    
    def build_game(self, output_dir=None):
        try:
            if not output_dir:
                output_dir = filedialog.askdirectory(title="Select output directory for game build")
                if not output_dir:
                    return False
        
            self.engine.log("Starting game build process...")
        
            # Проверяем, не запущены ли мы из EXE
            if getattr(sys, 'frozen', False):
                self.engine.log("Running from EXE - using standalone build method")
                return self._build_from_exe(output_dir)
            else:
                self.engine.log("Running from source - using PyInstaller")
                return self._build_from_source(output_dir)
            
        except Exception as e:
            self.engine.log(f"Build failed: {str(e)}")
            messagebox.showerror("Build Error", f"Failed to build game: {str(e)}")
            return False

    def _build_from_source(self, output_dir):
        """Билд из исходного кода через PyInstaller"""
        temp_dir = tempfile.mkdtemp()
        self.engine.log(f"Created temp directory: {temp_dir}")
    
        scene_data = SceneSerializer.serialize_scene(self.engine)
        scene_file = os.path.join(temp_dir, "scene.gemap")
        with open(scene_file, 'w', encoding='utf-8') as f:
            json.dump(scene_data, f, indent=2, ensure_ascii=False)
    
        game_code = self._generate_game_code()
        game_file = os.path.join(temp_dir, "game.py")
        with open(game_file, 'w', encoding='utf-8') as f:
            f.write(game_code)
    
        if not self._check_pyinstaller():
            self.engine.log("Installing PyInstaller...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
        self.engine.log("Building EXE with PyInstaller...")
    
        build_cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--console",
            "--name", "MyGame",
            "--add-data", f"{scene_file};.",
            "--distpath", output_dir,
            "--workpath", os.path.join(temp_dir, "build"),
            "--specpath", temp_dir,
            "--hidden-import", "tkinter",
            "--hidden-import", "json",
            "--hidden-import", "math",
            "--hidden-import", "random", 
            "--hidden-import", "time",
            "--hidden-import", "os",
            "--hidden-import", "sys",
            "--hidden-import", "re",
            game_file
        ]
    
        self.engine.log(f"Running PyInstaller command...")
    
        process = subprocess.Popen(build_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
    
        if stdout:
            self.engine.log(f"PyInstaller stdout: {stdout[:500]}...")
        if stderr:
            self.engine.log(f"PyInstaller stderr: {stderr[:500]}...")
    
        if process.returncode != 0:
            self.engine.log(f"PyInstaller error: {stderr}")
            raise Exception(f"PyInstaller failed with return code {process.returncode}")
    
        try:
            shutil.rmtree(temp_dir)
        except:
            self.engine.log("Warning: Could not remove temp directory")
    
        exe_path = os.path.join(output_dir, "MyGame.exe")
        if os.path.exists(exe_path):
            exe_size = os.path.getsize(exe_path) // 1024
            self.engine.log(f"Build completed successfully!")
            self.engine.log(f"EXE file: {exe_path}")
            self.engine.log(f"EXE size: {exe_size} KB")
        
            self._create_test_bat(output_dir)
        
            messagebox.showinfo("Build Complete", 
                            f"Game built successfully!\n\n"
                            f"EXE file: MyGame.exe\n"
                            f"Location: {output_dir}\n"
                            f"Size: {exe_size} KB")
            return True
        else:
            raise Exception("EXE file was not created")

    def _build_from_exe(self, output_dir):
        """Билд из EXE - создаем standalone Python скрипт"""
        try:
            self.engine.log("Creating standalone game package...")
        
            # Создаем папку для игры
            game_dir = os.path.join(output_dir, "MyGame")
            os.makedirs(game_dir, exist_ok=True)
        
            # Сохраняем сцену
            scene_data = SceneSerializer.serialize_scene(self.engine)
            scene_file = os.path.join(game_dir, "scene.gemap")
            with open(scene_file, 'w', encoding='utf-8') as f:
                json.dump(scene_data, f, indent=2, ensure_ascii=False)
        
            # Создаем основной файл игры
            game_code = self._generate_game_code()
            game_file = os.path.join(game_dir, "game.py")
            with open(game_file, 'w', encoding='utf-8') as f:
                f.write(game_code)
        
            # Создаем bat файл для запуска
            bat_content = '''@echo off
echo Starting GayEngine Game...
python game.py
pause
'''
            bat_file = os.path.join(game_dir, "run_game.bat")
            with open(bat_file, 'w') as f:
                f.write(bat_content)
        
            # Создаем инструкцию
            readme_content = '''GayEngine Game
===============

To play the game:

1. Make sure you have Python installed
2. Run 'run_game.bat' 
3. Or run manually: python game.py

Controls:
- WASD/Arrows: Move
- Space: Jump
- ESC: Exit
'''
            readme_file = os.path.join(game_dir, "README.txt")
            with open(readme_file, 'w') as f:
                f.write(readme_content)
        
            self.engine.log(f"Standalone game created in: {game_dir}")
            self.engine.log("Game includes: game.py, scene.gemap, run_game.bat, README.txt")
        
            messagebox.showinfo("Build Complete", 
                            f"Standalone game created!\n\n"
                            f"Location: {game_dir}\n"
                            f"Files created:\n"
                            f"- game.py (main game)\n"  
                            f"- scene.gemap (scene data)\n"
                            f"- run_game.bat (launcher)\n"
                            f"- README.txt (instructions)\n\n"
                            f"To play: Run 'run_game.bat' or 'python game.py'")
            return True
        
        except Exception as e:
            raise Exception(f"Failed to create standalone package: {str(e)}")
    
    def _check_pyinstaller(self):
        try:
            import PyInstaller
            self.engine.log(f"PyInstaller version: {PyInstaller.__version__}")
            return True
        except ImportError:
            return False
    
    def _create_test_bat(self, output_dir):
        """Создает bat файл для тестирования EXE"""
        bat_content = '''@echo off
echo ========================================
echo GayEngine Game Test Launcher
echo ========================================
echo.
echo Starting game...
echo If the game doesn't start, check the error messages below.
echo.
MyGame.exe
echo.
echo Game exited with error level %errorlevel%
echo.
pause
'''
        bat_path = os.path.join(output_dir, "test_game.bat")
        with open(bat_path, 'w') as f:
            f.write(bat_content)
        self.engine.log(f"Created test file: {bat_path}")
    
    def _generate_game_code(self):
        """Генерирует код для standalone игры с поддержкой GayScript и коллизий"""
        return '''import math
import time
import random
import tkinter as tk
import json
import os
import sys
import re

class Vector3:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z
    
    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
    
    def normalize(self):
        length = self.length()
        if length > 0:
            return Vector3(self.x / length, self.y / length, self.z / length)
        return Vector3()
    
    def rotate_x(self, angle):
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        y = self.y * cos_a - self.z * sin_a
        z = self.y * sin_a + self.z * cos_a
        return Vector3(self.x, y, z)
    
    def rotate_y(self, angle):
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        x = self.x * cos_a + self.z * sin_a
        z = -self.x * sin_a + self.z * cos_a
        return Vector3(x, self.y, z)
    
    def rotate_z(self, angle):
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        x = self.x * cos_a - self.y * sin_a
        y = self.x * sin_a + self.y * cos_a
        return Vector3(x, y, self.z)
    
    @staticmethod
    def from_dict(data):
        return Vector3(data["x"], data["y"], data["z"])

class Transform:
    def __init__(self):
        self.position = Vector3()
        self.rotation = Vector3()
        self.scale = Vector3(1, 1, 1)
    
    @staticmethod
    def from_dict(data):
        transform = Transform()
        transform.position = Vector3.from_dict(data["position"])
        transform.rotation = Vector3.from_dict(data["rotation"])
        transform.scale = Vector3.from_dict(data["scale"])
        return transform

class CollisionBox:
    def __init__(self, min_point, max_point):
        self.min = min_point
        self.max = max_point
    
    def intersects(self, other):
        return (self.min.x <= other.max.x and self.max.x >= other.min.x and
                self.min.y <= other.max.y and self.max.y >= other.min.y and
                self.min.z <= other.max.z and self.max.z >= other.min.z)
    
    def get_transformed(self, transform):
        half_size = Vector3(
            abs(self.max.x - self.min.x) * 0.5 * transform.scale.x,
            abs(self.max.y - self.min.y) * 0.5 * transform.scale.y,
            abs(self.max.z - self.min.z) * 0.5 * transform.scale.z
        )
        
        center = Vector3(
            transform.position.x,
            transform.position.y,
            transform.position.z
        )
        
        return CollisionBox(
            Vector3(center.x - half_size.x, center.y - half_size.y, center.z - half_size.z),
            Vector3(center.x + half_size.x, center.y + half_size.y, center.z + half_size.z)
        )

class Player:
    def __init__(self):
        self.transform = Transform()
        self.transform.position = Vector3(0, 1, 0)
        self.velocity = Vector3()
        self.on_ground = False
        self.move_speed = 5.0
        self.jump_force = 10.0
        self.rotation_speed = 2.0
        self.camera_height = 1.7
        self.collision_enabled = True
        self.collision_box = CollisionBox(Vector3(-0.4, 0, -0.4), Vector3(0.4, 2.0, 0.4))
        self.spin_speed = 2.0
        self.visual_object = None
    
    def update(self, pressed_keys, collidable_objects):
        # Поворот камеры
        if 'left' in pressed_keys:
            self.transform.rotation.y -= self.rotation_speed
        if 'right' in pressed_keys:
            self.transform.rotation.y += self.rotation_speed
        
        # Движение (поддерживаем и стрелки и WASD)
        direction = Vector3()
        if 'w' in pressed_keys or 'up' in pressed_keys:
            direction.z -= 1
        if 's' in pressed_keys or 'down' in pressed_keys:
            direction.z += 1
        if 'a' in pressed_keys:
            direction.x -= 1
        if 'd' in pressed_keys:
            direction.x += 1
        
        if direction.length() > 0:
            direction = direction.normalize()
            direction = direction.rotate_y(self.transform.rotation.y)
            
            # Двигаемся только если нет коллизии
            new_position = self.transform.position + direction * (self.move_speed * 0.1)
            if not self.check_collision(new_position, collidable_objects):
                self.transform.position = new_position
        
        # Прыжок
        if 'space' in pressed_keys and self.on_ground:
            self.velocity.y = self.jump_force * 0.1
            self.on_ground = False
        
        # Гравитация
        if not self.on_ground:
            self.velocity.y -= 0.015
            new_position = Vector3(
                self.transform.position.x,
                self.transform.position.y + self.velocity.y,
                self.transform.position.z
            )
            
            if not self.check_collision(new_position, collidable_objects):
                self.transform.position = new_position
            else:
                if self.velocity.y < 0:  # Падение вниз
                    self.on_ground = True
                self.velocity.y = 0
        
        # Проверяем, не упали ли мы ниже минимальной высоты
        if self.transform.position.y < -10:  # Упали в бездну
            self.transform.position = Vector3(0, 10, 0)  # Респавн
            self.velocity = Vector3()
            self.on_ground = False
            
        # Обновляем позицию визуального объекта
        if self.visual_object:
            self.visual_object.transform.position = self.transform.position
            self.visual_object.transform.rotation = self.transform.rotation
    
    def check_collision(self, new_position, collidable_objects):
        if not self.collision_enabled:
            return False
        
        # Создаем временный трансформ для проверки коллизии
        temp_transform = Transform()
        temp_transform.position = new_position
        temp_transform.scale = self.transform.scale
        
        player_box = self.collision_box.get_transformed(temp_transform)
        
        for obj in collidable_objects:
            if hasattr(obj, 'collision_enabled') and obj.collision_enabled and obj != self:
                obj_box = obj.collision_box.get_transformed(obj.transform)
                if player_box.intersects(obj_box):
                    return True
        
        return False
    
    def get_camera_position(self):
        return Vector3(
            self.transform.position.x,
            self.transform.position.y + self.camera_height,
            self.transform.position.z
        )
    
    def get_camera_rotation(self):
        return Vector3(0, self.transform.rotation.y, 0)

class GameObject:
    def __init__(self, name, shape="cube"):
        self.name = name
        self.shape = shape
        self.transform = Transform()
        self.color = "#FF0000"
        self.is_player = False
        self.collision_enabled = True
        
        # Создаем коллизию в зависимости от формы объекта
        if shape == "cube":
            self.collision_box = CollisionBox(Vector3(-0.5, -0.5, -0.5), Vector3(0.5, 0.5, 0.5))
        elif shape == "sphere":
            self.collision_box = CollisionBox(Vector3(-0.5, -0.5, -0.5), Vector3(0.5, 0.5, 0.5))
        else:
            self.collision_box = CollisionBox(Vector3(-0.5, -0.5, -0.5), Vector3(0.5, 0.5, 0.5))
    
    @staticmethod
    def from_dict(data):
        obj = GameObject(data["name"], data["shape"])
        obj.transform = Transform.from_dict(data["transform"])
        obj.color = data["color"]
        obj.is_player = data["is_player"]
        obj.collision_enabled = data.get("collision_enabled", True)
        return obj

class SimpleGayScriptInterpreter:
    def __init__(self, game_app):
        self.game_app = game_app
        self.scripts = []
    
    def load_script(self, script_content, script_name="Script"):
        try:
            script_data = {
                'name': script_name,
                'content': script_content,
                'parsed': True
            }
            self.scripts.append(script_data)
            print(f"Script loaded: {script_name}")
            return True
        except Exception as e:
            print(f"Script load error: {e}")
            return False
    
    def execute_all_scripts(self):
        for script in self.scripts:
            print(f"Executing script: {script['name']}")

class GameApp:
    def __init__(self):
        print("Starting GayEngine Game...")
        self.window = tk.Tk()
        self.window.title("My Game - Built with GayEngine")
        self.window.geometry("800x600")
        self.window.configure(bg='#1E1E1E')
        
        self.objects = []
        self.player = None
        self.pressed_keys = set()
        self.game_camera = Transform()
        self.game_camera.position = Vector3(0, -8, 3)
        self.game_camera.rotation = Vector3(-30, 0, 0)
        
        # Упрощенный GayScript интерпретатор
        self.script_interpreter = SimpleGayScriptInterpreter(self)
        
        self.canvas = tk.Canvas(self.window, bg='#1E1E1E', width=800, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.load_scene()
        self.setup_input()
        self.start_game_loop()
    
    def load_scene(self):
        """Загружает сцену из встроенного файла"""
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(__file__)
            
            scene_file = os.path.join(base_path, "scene.gemap")
            print(f"Loading scene from: {scene_file}")
            
            with open(scene_file, 'r', encoding='utf-8') as f:
                scene_data = json.load(f)
            
            # Загружаем объекты
            for obj_data in scene_data["objects"]:
                obj = GameObject.from_dict(obj_data)
                self.objects.append(obj)
                print(f"Loaded object: {obj.name}")
                
                if obj.is_player:
                    self.player = Player()
                    self.player.transform.position = obj.transform.position
                    self.player.visual_object = obj
                    print(f"Player created at: {self.player.transform.position}")
            
            # Загружаем скрипты
            if "gayscripts" in scene_data:
                for script_data in scene_data["gayscripts"]:
                    self.script_interpreter.load_script(script_data["content"], script_data["name"])
            
            print(f"Scene loaded: {len(self.objects)} objects, {len(self.script_interpreter.scripts)} scripts")
            
            # Выполняем скрипты при загрузке
            self.script_interpreter.execute_all_scripts()
            
        except Exception as e:
            print(f"Failed to load scene: {e}")
            self.create_default_scene()
    
    def create_default_scene(self):
        print("Creating default scene...")
        floor = GameObject("Plane")
        floor.transform.position = Vector3(0, 0, 0)
        floor.transform.scale = Vector3(10, 0.1, 10)
        floor.color = "#444444"
        self.objects.append(floor)
        
        cube = GameObject("Cube")
        cube.transform.position = Vector3(0, 0.5, 0)
        cube.color = "#FF0000"
        self.objects.append(cube)
        
        print("Default scene created")
    
    def setup_input(self):
        self.window.bind('<KeyPress>', self.on_key_press)
        self.window.bind('<KeyRelease>', self.on_key_release)
        self.window.focus_set()
        print("Input system initialized")
    
    def on_key_press(self, event):
        key = event.keysym.lower()
        key_mapping = {
            'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
            'w': 'w', 'a': 'a', 's': 's', 'd': 'd',
            'space': 'space'
        }
        key = key_mapping.get(key, key)
        self.pressed_keys.add(key)
    
    def on_key_release(self, event):
        key = event.keysym.lower()
        key_mapping = {
            'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
            'w': 'w', 'a': 'a', 's': 's', 'd': 'd',
            'space': 'space'
        }
        key = key_mapping.get(key, key)
        self.pressed_keys.discard(key)
    
    def project_3d_to_2d(self, position, camera_pos=None, camera_rot=None):
        if camera_pos is None:
            camera_pos = self.game_camera.position
        if camera_rot is None:
            camera_rot = self.game_camera.rotation
        
        pos = Vector3(
            position.x - camera_pos.x,
            position.y - camera_pos.y, 
            position.z - camera_pos.z
        )
        
        y_rad = math.radians(camera_rot.y)
        x_rad = math.radians(camera_rot.x)
        
        new_x = pos.x * math.cos(y_rad) + pos.z * math.sin(y_rad)
        new_z = -pos.x * math.sin(y_rad) + pos.z * math.cos(y_rad)
        
        new_y = pos.y * math.cos(x_rad) - new_z * math.sin(x_rad)
        final_z = pos.y * math.sin(x_rad) + new_z * math.cos(x_rad)
        
        if final_z > 0.1:
            factor = 50.0 / final_z
            x = new_x * factor + 400
            y = -new_y * factor + 300
            return (x, y)
        
        return (None, None)
    
    def draw_cube(self, obj, camera_pos, camera_rot):
        vertices = []
        for x in [-0.5, 0.5]:
            for y in [-0.5, 0.5]:
                for z in [-0.5, 0.5]:
                    vertex = Vector3(
                        x * obj.transform.scale.x + obj.transform.position.x,
                        y * obj.transform.scale.y + obj.transform.position.y, 
                        z * obj.transform.scale.z + obj.transform.position.z
                    )
                    vertices.append(vertex)
        
        edges = [
            (0,1), (1,3), (3,2), (2,0),
            (4,5), (5,7), (7,6), (6,4),
            (0,4), (1,5), (2,6), (3,7)
        ]
        
        for start, end in edges:
            p1 = self.project_3d_to_2d(vertices[start], camera_pos, camera_rot)
            p2 = self.project_3d_to_2d(vertices[end], camera_pos, camera_rot)
            
            if p1 and p2 and p1[0] is not None and p2[0] is not None:
                try:
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], 
                                          fill=obj.color, width=2)
                except Exception:
                    pass
    
    def draw_sphere(self, obj, camera_pos, camera_rot):
        center_2d = self.project_3d_to_2d(obj.transform.position, camera_pos, camera_rot)
        if center_2d and center_2d[0] is not None:
            try:
                radius = 20 * obj.transform.scale.x
                self.canvas.create_oval(center_2d[0]-radius, center_2d[1]-radius, 
                                      center_2d[0]+radius, center_2d[1]+radius, 
                                      outline=obj.color, width=2)
            except Exception:
                pass
    
    def draw_scene(self):
        self.canvas.delete("all")
        
        if self.player:
            camera_pos = self.player.get_camera_position()
            camera_rot = self.player.get_camera_rotation()
        else:
            camera_pos = self.game_camera.position
            camera_rot = self.game_camera.rotation
        
        for obj in self.objects:
            if obj.shape == "cube":
                self.draw_cube(obj, camera_pos, camera_rot)
            elif obj.shape == "sphere":
                self.draw_sphere(obj, camera_pos, camera_rot)
        
        info = f"Objects: {len(self.objects)} | Press ESC to exit"
        if self.player:
            info += f" | Pos: ({self.player.transform.position.x:.1f}, {self.player.transform.position.y:.1f}, {self.player.transform.position.z:.1f})"
        
        self.canvas.create_text(10, 10, text=info, anchor='nw', fill='white', font=('Arial', 10))
        
        if self.player:
            controls = "WASD/Arrows: Move, Space: Jump"
            self.canvas.create_text(10, 30, text=controls, anchor='nw', fill='#00FF00', font=('Arial', 9))
        else:
            controls = "Fly Camera Mode"
            self.canvas.create_text(10, 30, text=controls, anchor='nw', fill='#CCCCCC', font=('Arial', 9))
    
    def update(self):
        if self.player:
            collidable_objects = [obj for obj in self.objects if hasattr(obj, 'collision_enabled') and obj.collision_enabled]
            self.player.update(self.pressed_keys, collidable_objects)
        
        self.draw_scene()
        self.window.after(16, self.update)
    
    def start_game_loop(self):
        print("Starting game loop...")
        self.update()
    
    def run(self):
        print("Game is running...")
        self.window.mainloop()

if __name__ == "__main__":
    print("Starting game built with GayEngine...")
    app = GameApp()
    app.run()
'''

class EngineBuilder:
    def __init__(self, engine):
        self.engine = engine
    
    def build_engine(self, output_dir=None):
        try:
            if not output_dir:
                output_dir = filedialog.askdirectory(title="Select output directory for GayEngine EXE")
                if not output_dir:
                    return False
            
            self.engine.log("Starting GayEngine build process...")
            
            temp_dir = tempfile.mkdtemp()
            self.engine.log(f"Created temp directory: {temp_dir}")
            
            current_file = __file__
            engine_file = os.path.join(temp_dir, "gayengine.py")
            
            with open(current_file, 'r', encoding='utf-8') as source:
                with open(engine_file, 'w', encoding='utf-8') as target:
                    target.write(source.read())
            
            if not self._check_pyinstaller():
                self.engine.log("Installing PyInstaller...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            
            self.engine.log("Building GayEngine EXE with PyInstaller...")
            
            build_cmd = [
                sys.executable, "-m", "PyInstaller",
                "--onefile",
                "--noconsole",
                "--name", "GayEngine",
                "--distpath", output_dir,
                "--workpath", os.path.join(temp_dir, "build"),
                "--specpath", temp_dir,
                engine_file
            ]
            
            process = subprocess.Popen(build_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                self.engine.log(f"PyInstaller error: {stderr}")
                if "No module named" in stderr:
                    module_error = stderr.split("No module named")[-1].split("\\n")[0].strip()
                    self.engine.log(f"Missing module: {module_error}")
                    messagebox.showerror("Build Error", f"Missing module: {module_error}\\n\\nTry installing it with: pip install {module_error}")
                else:
                    raise Exception(f"PyInstaller failed with return code {process.returncode}")
            
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
            
            exe_path = os.path.join(output_dir, "GayEngine.exe")
            if os.path.exists(exe_path):
                self.engine.log(f"GayEngine build completed successfully!")
                self.engine.log(f"EXE file: {exe_path}")
                self.engine.log(f"Output directory: {output_dir}")
                
                messagebox.showinfo("Build Complete", 
                                  f"GayEngine built successfully!\\n\\n"
                                  f"EXE file: GayEngine.exe\\n"
                                  f"Location: {output_dir}\\n\\n"
                                  f"You can now share this EXE with your friends!")
                return True
            else:
                raise Exception("GayEngine EXE file was not created")
            
        except Exception as e:
            self.engine.log(f"GayEngine build failed: {str(e)}")
            messagebox.showerror("Build Error", f"Failed to build GayEngine: {str(e)}")
            return False
    
    def _check_pyinstaller(self):
        try:
            import PyInstaller
            return True
        except ImportError:
            return False

class GayEngine:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("GayEngine - Untitled")
        self.window.geometry("1400x900")
        self.window.configure(bg='#2D2D30')
        
        self.tool_mode = "select"
        self.objects = []
        self.selected_object = None
        self.player = None
        self.game_mode = False
        self.current_file = None
        self.builder = GameBuilder(self)
        self.engine_builder = EngineBuilder(self)
        
        self.script_interpreter = GayScriptInterpreter(self)
        self.script_windows = {}
        
        self.scene_camera = Transform()
        self.scene_camera.position = Vector3(0, -8, 3)
        self.scene_camera.rotation = Vector3(-30, 0, 0)
        self.scene_camera_speed = 0.3
        
        self.pressed_keys = set()
        self.mouse_pressed = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.right_mouse_pressed = False
        
        self.zbuffer = ZBuffer(800, 600)
        self.texture_manager = TextureManager()
        self.render_mode = "wireframe"
        
        self.create_interface()
        self.create_menu()
        self.create_default_scene()
        
        self.bind_events()
        self.start_loop()

    def create_menu(self):
        menubar = tk.Menu(self.window, bg='#2D2D30', fg='white')
        
        file_menu = tk.Menu(menubar, tearoff=0, bg='#2D2D30', fg='white')
        file_menu.add_command(label="New Scene", command=self.new_scene)
        file_menu.add_command(label="Open Scene...", command=self.load_scene)
        file_menu.add_command(label="Save Scene", command=self.save_scene)
        file_menu.add_command(label="Save Scene As...", command=self.save_scene_as)
        file_menu.add_separator()
        file_menu.add_command(label="Build Game...", command=self.build_game)
        file_menu.add_command(label="Build Engine...", command=self.build_engine)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.window.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        object_menu = tk.Menu(menubar, tearoff=0, bg='#2D2D30', fg='white')
        object_menu.add_command(label="Create Empty", command=self.create_empty)
        object_menu.add_command(label="3D Object -> Cube", command=self.create_cube)
        object_menu.add_command(label="3D Object -> Sphere", command=self.create_sphere)
        object_menu.add_separator()
        object_menu.add_command(label="Create Player", command=self.create_player)
        menubar.add_cascade(label="GameObject", menu=object_menu)
        
        script_menu = tk.Menu(menubar, tearoff=0, bg='#2D2D30', fg='white')
        script_menu.add_command(label="Load GayScript...", command=self.load_gayscript)
        script_menu.add_command(label="Create New Script", command=self.create_new_script)
        script_menu.add_separator()
        script_menu.add_command(label="Scripts Manager", command=self.show_scripts_manager)
        menubar.add_cascade(label="GayScript", menu=script_menu)
        
        self.window.config(menu=menubar)

    def create_interface(self):
        toolbar = Frame(self.window, bg='#3E3E42', height=40)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        
        self.render_btn = Button(toolbar, text="🎨 Texture", command=self.toggle_render_mode,
                                bg='#FF9800', fg='white', relief='flat', padx=10)
        self.render_btn.pack(side=tk.LEFT, padx=2)
        
        tools = [
            ("👆", "select", self.set_select_mode),
            ("↔", "move", self.set_move_mode),
            ("🔄", "rotate", self.set_rotate_mode),
            ("📏", "scale", self.set_scale_mode)
        ]
        
        for text, mode, command in tools:
            btn = Button(toolbar, text=text, command=command,
                        bg='#007ACC' if mode == self.tool_mode else '#5A5A5A', 
                        fg='white', relief='flat', width=3)
            btn.pack(side=tk.LEFT, padx=2)
        
        self.play_button = Button(toolbar, text="▶ Play", command=self.toggle_game_mode,
                                 bg='#4CAF50', fg='white', relief='flat', padx=10)
        self.play_button.pack(side=tk.LEFT, padx=10)
        
        self.script_button = Button(toolbar, text="📜 GayScript", command=self.show_scripts_manager,
                                   bg='#9C27B0', fg='white', relief='flat', padx=10)
        self.script_button.pack(side=tk.LEFT, padx=5)
        
        self.build_button = Button(toolbar, text="🔨 Build Game", command=self.build_game,
                                  bg='#9C27B0', fg='white', relief='flat', padx=10)
        self.build_button.pack(side=tk.LEFT, padx=5)
        
        self.build_engine_btn = Button(toolbar, text="🚀 Build Engine", command=self.build_engine,
                                     bg='#FF5722', fg='white', relief='flat', padx=10)
        self.build_engine_btn.pack(side=tk.LEFT, padx=5)
        
        self.camera_info = Label(toolbar, text="Camera: (0, -8, 3)", bg='#3E3E42', fg='white', font=('Arial', 9))
        self.camera_info.pack(side=tk.RIGHT, padx=10)
        
        logo = Label(toolbar, text="GayEngine", bg='#3E3E42', fg='white', font=('Arial', 10, 'bold'))
        logo.pack(side=tk.RIGHT, padx=10)
        
        main_frame = Frame(self.window, bg='#2D2D30')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.create_hierarchy(main_frame)
        self.create_scene(main_frame)
        self.create_inspector(main_frame)
        self.create_console()

    def create_hierarchy(self, parent):
        frame = Frame(parent, width=250, bg='#2D2D30')
        frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        title = Label(frame, text="Hierarchy", bg='#3E3E42', fg='white', 
                     font=('Arial', 10, 'bold'), pady=8)
        title.pack(fill=tk.X)
        
        self.object_list = tk.Listbox(frame, bg='#1E1E1E', fg='white', 
                                    selectbackground='#007ACC', font=('Arial', 10))
        self.object_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.object_list.bind('<<ListboxSelect>>', self.select_object_from_list)

    def create_scene(self, parent):
        frame = Frame(parent, bg='#252526')
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        title = Label(frame, text="Scene View", bg='#3E3E42', fg='white', 
                     font=('Arial', 10, 'bold'), pady=8)
        title.pack(fill=tk.X)
        
        self.scene_canvas = Canvas(frame, bg='#1E1E1E', width=800, height=600)
        self.scene_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.scene_canvas.bind("<Button-1>", self.handle_scene_click)
        self.scene_canvas.bind("<B1-Motion>", self.handle_mouse_drag)
        self.scene_canvas.bind("<Button-3>", self.handle_right_click)
        self.scene_canvas.bind("<B3-Motion>", self.handle_camera_rotate)
        self.scene_canvas.bind("<MouseWheel>", self.handle_mouse_wheel)
        self.scene_canvas.bind("<Enter>", lambda e: self.scene_canvas.focus_set())

    def create_inspector(self, parent):
        frame = Frame(parent, width=300, bg='#2D2D30')
        frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        title = Label(frame, text="Inspector", bg='#3E3E42', fg='white', 
                     font=('Arial', 10, 'bold'), pady=8)
        title.pack(fill=tk.X)
        
        self.inspector_notebook = ttk.Notebook(frame)
        self.inspector_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.object_tab = Frame(self.inspector_notebook, bg='#2D2D30')
        self.inspector_notebook.add(self.object_tab, text="Object")
        
        self.scripts_tab = Frame(self.inspector_notebook, bg='#2D2D30')
        self.inspector_notebook.add(self.scripts_tab, text="Scripts")
        
        self.inspector_content = Frame(self.object_tab, bg='#2D2D30')
        self.inspector_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.scripts_content = Frame(self.scripts_tab, bg='#2D2D30')
        self.scripts_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_console(self):
        frame = Frame(self.window, height=150, bg='#1E1E1E')
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        title = Label(frame, text="Console", bg='#3E3E42', fg='white', 
                     font=('Arial', 10, 'bold'), pady=8)
        title.pack(fill=tk.X)
        
        self.console_text = tk.Text(frame, bg='#1E1E1E', fg='#CCCCCC', height=6, font=('Consolas', 9))
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log("GayEngine started with FULL GayScript v2.0 support!")
        self.log("Features: Multiple Working, Using objects, Collision detection, Line fields")
        self.log("Use File -> Build Game to create standalone games")

    def create_default_scene(self):
        floor = GameObject("Plane")
        floor.transform.position = Vector3(0, 0, 0)
        floor.transform.scale = Vector3(10, 0.1, 10)
        floor.color = "#444444"
        self.add_object(floor)
        
        cube1 = GameObject("Red_Cube")
        cube1.transform.position = Vector3(-2, 0.5, 0)
        cube1.color = "#FF0000"
        self.add_object(cube1)
        
        cube2 = GameObject("Green_Cube")
        cube2.transform.position = Vector3(0, 0.5, 0)
        cube2.color = "#00FF00"
        self.add_object(cube2)
        
        cube3 = GameObject("Blue_Cube")
        cube3.transform.position = Vector3(2, 0.5, 0)
        cube3.color = "#0000FF"
        self.add_object(cube3)
        
        self.select_object(cube1)
        self.log("Default scene created with collision-enabled objects")

    def update_inspector(self):
        for widget in self.inspector_content.winfo_children():
            widget.destroy()
        for widget in self.scripts_content.winfo_children():
            widget.destroy()
        
        if not self.selected_object:
            return
        
        obj = self.selected_object
        
        title = Label(self.inspector_content, text=obj.name, bg='#2D2D30', fg='white',
                     font=('Arial', 12, 'bold'))
        title.pack(anchor='w', pady=(0, 10))
        
        self.create_transform_component(obj)
        self.create_collision_component(obj)
        self.create_scripts_component(obj)

    def create_transform_component(self, obj):
        frame = Frame(self.inspector_content, bg='#2D2D30')
        frame.pack(fill=tk.X, pady=5)
        
        header = Frame(frame, bg='#3E3E42')
        header.pack(fill=tk.X)
        Label(header, text="Transform", bg='#3E3E42', fg='white',
              font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5, pady=2)
        
        self.create_vector_property(frame, "Position", obj.transform.position)
        self.create_vector_property(frame, "Rotation", obj.transform.rotation)
        self.create_vector_property(frame, "Scale", obj.transform.scale)

    def create_collision_component(self, obj):
        frame = Frame(self.inspector_content, bg='#2D2D30')
        frame.pack(fill=tk.X, pady=5)
        
        header = Frame(frame, bg='#3E3E42')
        header.pack(fill=tk.X)
        Label(header, text="Collision", bg='#3E3E42', fg='white',
              font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5, pady=2)
        
        collision_frame = Frame(frame, bg='#2D2D30')
        collision_frame.pack(fill=tk.X, padx=10, pady=5)
        
        Label(collision_frame, text="Enabled:", bg='#2D2D30', fg='white').pack(side=tk.LEFT)
        
        collision_var = tk.BooleanVar(value=obj.collision_enabled)
        collision_cb = tk.Checkbutton(collision_frame, variable=collision_var, 
                                     bg='#2D2D30', fg='white', selectcolor='#007ACC',
                                     command=lambda: self.toggle_collision(obj, collision_var.get()))
        collision_cb.pack(side=tk.LEFT, padx=5)

    def toggle_collision(self, obj, enabled):
        obj.collision_enabled = enabled
        self.log(f"{obj.name} collision: {'enabled' if enabled else 'disabled'}")

    def create_vector_property(self, parent, name, vector):
        frame = Frame(parent, bg='#2D2D30')
        frame.pack(fill=tk.X, padx=10, pady=2)
        
        Label(frame, text=name, bg='#2D2D30', fg='white', width=8).pack(side=tk.LEFT)
        
        for i, axis in enumerate(['X', 'Y', 'Z']):
            Frame(frame, bg='#2D2D30', width=5).pack(side=tk.LEFT)
            value = getattr(vector, axis.lower())
            Entry(frame, bg='#1E1E1E', fg='white', insertbackground='white',
                  width=8, relief='sunken').pack(side=tk.LEFT)

    def create_scripts_component(self, obj):
        title = Label(self.scripts_content, text="GayScripts", bg='#2D2D30', fg='white',
                     font=('Arial', 12, 'bold'))
        title.pack(anchor='w', pady=(0, 10))
        
        object_scripts = []
        for script in self.script_interpreter.scripts:
            for target_path in script['target_objects']:
                if obj.name in target_path:
                    object_scripts.append(script)
                    break
        
        if not object_scripts:
            Label(self.scripts_content, text="No scripts attached", 
                  bg='#2D2D30', fg='#666666').pack(pady=10)
            return
        
        for script in object_scripts:
            script_frame = Frame(self.scripts_content, bg='#3E3E42', relief='raised', bd=1)
            script_frame.pack(fill=tk.X, pady=2)
            
            Label(script_frame, text=script['name'], bg='#3E3E42', fg='white',
                  font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5, pady=2)
            
            Button(script_frame, text="Edit", command=lambda s=script: self.edit_script(s),
                  bg='#007ACC', fg='white', relief='flat', width=6).pack(side=tk.RIGHT, padx=2, pady=2)
            
            self.create_script_fields(script, self.scripts_content)

    def create_script_fields(self, script, parent):
        if not script['line_definitions']:
            return
        
        fields_frame = Frame(parent, bg='#2D2D30')
        fields_frame.pack(fill=tk.X, pady=5)
        
        for field_id, field_data in script['line_definitions'].items():
            field_frame = Frame(fields_frame, bg='#2D2D30')
            field_frame.pack(fill=tk.X, padx=10, pady=2)
            
            label_text = field_data['label']
            if field_data.get('target_property'):
                label_text += f" → {field_data['target_property']}"
            
            Label(field_frame, text=label_text, bg='#2D2D30', fg='white').pack(anchor='w')
            
            entry = Entry(field_frame, bg='#1E1E1E', fg='white', insertbackground='white')
            entry.pack(fill=tk.X, pady=2)
            entry.insert(0, field_data.get('value', field_data.get('initial_value', '')))
            
            entry.bind('<KeyRelease>', 
                      lambda e, s=script, fid=field_id: self.update_script_field(s, fid, e.widget.get()))

    def update_script_field(self, script, field_id, value):
        self.script_interpreter.update_line_field(script, field_id, value)
        
        if self.game_mode:
            self.script_interpreter.execute_script(script)

    def load_gayscript(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("GayScript files", "*.gayscript"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Load GayScript"
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            script_name = os.path.basename(file_path)
            if self.script_interpreter.load_script(script_content, script_name):
                self.log(f"GayScript loaded: {script_name}")
                self.update_inspector()
            else:
                messagebox.showerror("Script Error", "Failed to parse GayScript")
                
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load script: {str(e)}")

    def create_new_script(self):
        script_window = tk.Toplevel(self.window)
        script_window.title("New GayScript")
        script_window.geometry("600x400")
        script_window.configure(bg='#2D2D30')
        
        editor_frame = Frame(script_window, bg='#2D2D30')
        editor_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        Label(editor_frame, text="GayScript Editor", bg='#2D2D30', fg='white',
              font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        
        text_widget = tk.Text(editor_frame, bg='#1E1E1E', fg='white', insertbackground='white',
                             font=('Consolas', 10), wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        template = '''GameScript
Working Hierarchy.Player
Working Hierarchy.Green_Cube
{
using Player:
using Green_Cube:

line "Player Speed"
line.ask Player.Speed
Player.Speed = [line]

line "Jump Force" 
line.ask Player.JumpForce
Player.JumpForce = [line]

line "Camera Rotation Speed"
line.ask Player.CameraRotationSpeed  
Player.CameraRotationSpeed = [line]

# Collision detection example
Block.Color = 255, 255, 255
if Player.Colision == Green_Cube
    Block.Color = 255, 0, 0
else
    Block.Color = 255, 255, 255
}'''
        text_widget.insert('1.0', template)
        
        button_frame = Frame(editor_frame, bg='#2D2D30')
        button_frame.pack(fill=tk.X, pady=10)
        
        def save_script():
            content = text_widget.get('1.0', tk.END)
            script_name = f"Script_{len(self.script_interpreter.scripts) + 1}"
            if self.script_interpreter.load_script(content, script_name):
                self.log(f"New GayScript created: {script_name}")
                script_window.destroy()
                self.update_inspector()
            else:
                messagebox.showerror("Script Error", "Invalid GayScript syntax")
        
        Button(button_frame, text="Save Script", command=save_script,
               bg='#4CAF50', fg='white', relief='flat').pack(side=tk.RIGHT, padx=5)
        
        Button(button_frame, text="Cancel", command=script_window.destroy,
               bg='#F44336', fg='white', relief='flat').pack(side=tk.RIGHT, padx=5)

    def edit_script(self, script_data):
        script_window = tk.Toplevel(self.window)
        script_window.title(f"Edit {script_data['name']}")
        script_window.geometry("600x400")
        script_window.configure(bg='#2D2D30')
        
        editor_frame = Frame(script_window, bg='#2D2D30')
        editor_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        Label(editor_frame, text=f"Editing: {script_data['name']}", bg='#2D2D30', fg='white',
              font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        
        text_widget = tk.Text(editor_frame, bg='#1E1E1E', fg='white', insertbackground='white',
                             font=('Consolas', 10), wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert('1.0', script_data['content'])
        
        button_frame = Frame(editor_frame, bg='#2D2D30')
        button_frame.pack(fill=tk.X, pady=10)
        
        def save_changes():
            content = text_widget.get('1.0', tk.END)
            script_data['content'] = content
            self.script_interpreter.scripts.remove(script_data)
            if self.script_interpreter.load_script(content, script_data['name']):
                self.log(f"GayScript updated: {script_data['name']}")
                script_window.destroy()
                self.update_inspector()
            else:
                messagebox.showerror("Script Error", "Invalid GayScript syntax")
        
        Button(button_frame, text="Save Changes", command=save_changes,
               bg='#4CAF50', fg='white', relief='flat').pack(side=tk.RIGHT, padx=5)
        
        Button(button_frame, text="Cancel", command=script_window.destroy,
               bg='#F44336', fg='white', relief='flat').pack(side=tk.RIGHT, padx=5)

    def show_scripts_manager(self):
        manager_window = tk.Toplevel(self.window)
        manager_window.title("GayScript Manager")
        manager_window.geometry("700x500")
        manager_window.configure(bg='#2D2D30')
        
        title = Label(manager_window, text="GayScript Manager", bg='#3E3E42', fg='white',
                     font=('Arial', 12, 'bold'), pady=10)
        title.pack(fill=tk.X)
        
        examples_frame = Frame(manager_window, bg='#2D2D30')
        examples_frame.pack(fill=tk.X, padx=10, pady=5)
        
        Label(examples_frame, text="New Features:", bg='#2D2D30', fg='#CCCCCC',
              font=('Arial', 10, 'bold')).pack(anchor='w')
        
        examples = [
            "Multiple Working: Working Hierarchy.Player + Working Hierarchy.Cube",
            "Using objects: using Player: using Cube:",
            "Collision detection: if Player.Colision == Cube",
            "Collision control: Player.Colision = false / Block.Colision = true",
            "Line fields: line \"Label\" + line.ask + Property = [line]"
        ]
        
        for example in examples:
            Label(examples_frame, text=f"• {example}", bg='#2D2D30', fg='#888888',
                  font=('Arial', 8)).pack(anchor='w')
        
        list_frame = Frame(manager_window, bg='#2D2D30')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for i, script in enumerate(self.script_interpreter.scripts):
            script_frame = Frame(list_frame, bg='#3E3E42', relief='raised', bd=1)
            script_frame.pack(fill=tk.X, pady=2)
            
            Label(script_frame, text=script['name'], bg='#3E3E42', fg='white',
                  font=('Arial', 10)).pack(side=tk.LEFT, padx=5, pady=5)
            
            targets = ", ".join(script['target_objects'])
            Label(script_frame, text=targets or "No targets", 
                  bg='#3E3E42', fg='#CCCCCC', font=('Arial', 8)).pack(side=tk.LEFT, padx=5)
            
            if script['line_definitions']:
                fields_info = f"{len(script['line_definitions'])} fields"
                Label(script_frame, text=fields_info, bg='#3E3E42', fg='#90CAF9',
                      font=('Arial', 8)).pack(side=tk.LEFT, padx=5)
            
            Button(script_frame, text="Edit", 
                  command=lambda s=script: self.edit_script(s),
                  bg='#007ACC', fg='white', relief='flat', width=6).pack(side=tk.RIGHT, padx=2)
            
            Button(script_frame, text="Delete", 
                  command=lambda s=script: self.delete_script(s),
                  bg='#F44336', fg='white', relief='flat', width=6).pack(side=tk.RIGHT, padx=2)
        
        button_frame = Frame(manager_window, bg='#2D2D30')
        button_frame.pack(fill=tk.X, pady=10, padx=10)
        
        Button(button_frame, text="New Script", command=self.create_new_script,
               bg='#4CAF50', fg='white', relief='flat').pack(side=tk.LEFT, padx=5)
        
        Button(button_frame, text="Load Script", command=self.load_gayscript,
               bg='#2196F3', fg='white', relief='flat').pack(side=tk.LEFT, padx=5)
        
        Button(button_frame, text="Collision Example", 
               command=self.create_collision_example_script,
               bg='#FF9800', fg='white', relief='flat').pack(side=tk.LEFT, padx=5)
        
        Button(button_frame, text="Close", command=manager_window.destroy,
               bg='#666666', fg='white', relief='flat').pack(side=tk.RIGHT, padx=5)

    def create_collision_example_script(self):
        script_content = '''GameScript
Working Hierarchy.Player
Working Hierarchy.Green_Cube
{
using Player:
using Green_Cube:

# Player controls
line "Movement Speed"
line.ask Player.Speed
Player.Speed = [line]

line "Jump Power"
line.ask Player.JumpForce  
Player.JumpForce = [line]

line "Camera Rotation Speed"
line.ask Player.CameraRotationSpeed
Player.CameraRotationSpeed = [line]

# Cube appearance
line "Cube Color (r,g,b)"
line.ask Block.Color
Block.Color = [line]

# Collision detection
Block.Color = 0, 255, 0  # Default green
if Player.Colision == Green_Cube
    Block.Color = 255, 0, 0  # Red on collision
else
    Block.Color = 0, 255, 0  # Green otherwise
}'''
        
        script_name = "CollisionDemo"
        if self.script_interpreter.load_script(script_content, script_name):
            self.log(f"Collision example script created: {script_name}")
            self.update_inspector()
        else:
            messagebox.showerror("Script Error", "Failed to create collision example script")

    def delete_script(self, script_data):
        self.script_interpreter.scripts.remove(script_data)
        self.log(f"GayScript deleted: {script_data['name']}")
        self.update_inspector()
        for window in self.window.winfo_children():
            if isinstance(window, tk.Toplevel) and "GayScript Manager" in window.title():
                window.destroy()
        self.show_scripts_manager()

    def set_select_mode(self):
        self.tool_mode = "select"
        self.log("Tool: Select")
    
    def set_move_mode(self):
        self.tool_mode = "move"
        self.log("Tool: Move")
    
    def set_rotate_mode(self):
        self.tool_mode = "rotate"
        self.log("Tool: Rotate")
    
    def set_scale_mode(self):
        self.tool_mode = "scale"
        self.log("Tool: Scale")
    
    def toggle_render_mode(self):
        self.render_mode = "textured" if self.render_mode == "wireframe" else "wireframe"
        self.render_btn.config(text="Wireframe" if self.render_mode == "wireframe" else "Texture")
        self.log(f"Render mode: {self.render_mode}")
    
    def toggle_game_mode(self):
        self.game_mode = not self.game_mode
        if self.game_mode:
            self.play_button.config(text="⏹ Stop", bg='#F44336')
            self.log("Entering Play Mode!")
        
            self.pressed_keys.clear()
        
            self.player = None
            player_obj = None
        
            for obj in self.objects:
                if obj.is_player:
                    player_obj = obj
                    self.player = Player()
                    self.player.transform.position = obj.transform.position
                    self.player.transform.rotation = obj.transform.rotation
                    self.player.transform.scale = obj.transform.scale
                    # СВЯЗЫВАЕМ ВИЗУАЛЬНЫЙ ОБЪЕКТ С ФИЗИЧЕСКИМ ИГРОКОМ
                    self.player.visual_object = player_obj
                    self.log(f"Player spawned at: {self.player.transform.position}")
                    break
        
            if not self.player:
                self.log("No Player object found! Create one from GameObject menu.")
                self.game_mode = False
                self.play_button.config(text="▶ Play", bg='#4CAF50')
            else:
                self._player_object = player_obj
                self.script_interpreter.execute_all_scripts(apply_initial_values=True)
        else:
            self.play_button.config(text="▶ Play", bg='#4CAF50')
            self.log("Exiting Play Mode")

    def build_engine(self):
        self.log("Starting GayEngine EXE build process...")
        self.engine_builder.build_engine()

    def build_game(self):
        if not self.objects:
            messagebox.showwarning("Build Warning", "Scene is empty! Add some objects before building.")
            return
        
        has_player = any(obj.is_player for obj in self.objects)
        if not has_player:
            result = messagebox.askyesno(
                "No Player Object", 
                "No player object found in scene. The game will start in fly-camera mode.\n\nDo you want to continue building?"
            )
            if not result:
                return
        
        self.log("Starting game build process...")
        
        output_dir = filedialog.askdirectory(title="Select output directory for game build")
        if not output_dir:
            return
            
        self.builder.build_game(output_dir)

    def save_scene(self):
        if self.current_file:
            file_path = self.current_file
        else:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".gemap",
                filetypes=[("GayEngine Map files", "*.gemap"), ("All files", "*.*")],
                title="Save Scene As"
            )
            if not file_path:
                return
        
        try:
            scene_data = SceneSerializer.serialize_scene(self)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(scene_data, f, indent=2, ensure_ascii=False)
            
            self.current_file = file_path
            filename = os.path.basename(file_path)
            self.window.title(f"GayEngine - {filename}")
            self.log(f"Scene saved successfully: {filename}")
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save scene: {str(e)}")
            self.log(f"Save failed: {str(e)}")

    def save_scene_as(self):
        self.current_file = None
        self.save_scene()

    def load_scene(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("GayEngine Map files", "*.gemap"), ("All files", "*.*")],
            title="Load Scene"
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                scene_data = json.load(f)
            
            SceneSerializer.deserialize_scene(self, scene_data)
            
            self.current_file = file_path
            filename = os.path.basename(file_path)
            self.window.title(f"GayEngine - {filename}")
            self.log(f"Scene loaded successfully: {filename}")
            self.update_inspector()
            
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load scene: {str(e)}")
            self.log(f"Load failed: {str(e)}")

    def add_object(self, obj):
        self.objects.append(obj)
        self.object_list.insert(tk.END, obj.name)
        self.log(f"Created: {obj.name} (collision: {'enabled' if obj.collision_enabled else 'disabled'})")

    def select_object(self, obj):
        if self.selected_object:
            self.selected_object.selected = False
        self.selected_object = obj
        if obj:
            obj.selected = True
        self.update_inspector()

    def select_object_from_list(self, event):
        selection = self.object_list.curselection()
        if selection:
            index = selection[0]
            self.select_object(self.objects[index])

    def create_empty(self):
        obj = GameObject("GameObject")
        self.add_object(obj)
        self.select_object(obj)

    def create_cube(self):
        obj = GameObject("Cube", "cube")
        obj.transform.position = Vector3(0, 0.5, 0)
        self.add_object(obj)
        self.select_object(obj)

    def create_sphere(self):
        obj = GameObject("Sphere", "sphere")
        obj.transform.position = Vector3(0, 0.5, 0)
        self.add_object(obj)
        self.select_object(obj)

    def create_player(self):
        player_obj = GameObject("Player", "cube")
        player_obj.transform.position = Vector3(0, 1, 0)
        player_obj.transform.scale = Vector3(0.8, 2.0, 0.8)
        player_obj.color = "#FF6B6B"
        player_obj.is_player = True
        self.add_object(player_obj)
        self.select_object(player_obj)
        self.log("Player object created with collision!")
        self.log("Select Player and press Play for first-person view with collision detection")

    def log(self, message):
        self.console_text.insert(tk.END, f"{message}\n")
        self.console_text.see(tk.END)

    def bind_events(self):
        self.window.bind('<KeyPress>', self.handle_key_press)
        self.window.bind('<KeyRelease>', self.handle_key_release)
        self.window.bind('<FocusIn>', lambda e: self.focus_gained())
        self.window.focus_set()

    def handle_key_press(self, event):
        key = event.keysym.lower()
        key_mapping = {
            'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
            'w': 'w', 'a': 'a', 's': 's', 'd': 'd',
            'space': 'space', 'shift_l': 'shift'
        }
        key = key_mapping.get(key, key)
        self.pressed_keys.add(key)

    def handle_key_release(self, event):
        key = event.keysym.lower()
        key_mapping = {
            'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
            'w': 'w', 'a': 'a', 's': 's', 'd': 'd',
            'space': 'space', 'shift_l': 'shift'
        }
        key = key_mapping.get(key, key)
        self.pressed_keys.discard(key)

    def handle_scene_click(self, event):
        self.mouse_pressed = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def handle_right_click(self, event):
        self.right_mouse_pressed = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def handle_mouse_drag(self, event):
        if self.mouse_pressed and self.selected_object and not self.game_mode:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            
            if self.tool_mode == "move":
                self.selected_object.transform.position.x += dx * 0.01
                self.selected_object.transform.position.y -= dy * 0.01
            elif self.tool_mode == "rotate":
                self.selected_object.transform.rotation.y += dx * 0.5
                self.selected_object.transform.rotation.x += dy * 0.5
            elif self.tool_mode == "scale":
                scale = 1 + dy * 0.01
                self.selected_object.transform.scale = Vector3(
                    self.selected_object.transform.scale.x * scale,
                    self.selected_object.transform.scale.y * scale,
                    self.selected_object.transform.scale.z * scale
                )
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.update_inspector()

    def handle_camera_rotate(self, event):
        if self.right_mouse_pressed and not self.game_mode:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            
            self.scene_camera.rotation.y += dx * 0.3
            self.scene_camera.rotation.x += dy * 0.3
            self.scene_camera.rotation.x = max(-89, min(89, self.scene_camera.rotation.x))
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y

    def handle_mouse_wheel(self, event):
        if not self.game_mode:
            self.scene_camera.position.z += event.delta * 0.01

    def focus_gained(self):
        self.pressed_keys.clear()

    def update_scene_camera(self):
        direction = Vector3()
        
        if 'w' in self.pressed_keys:
            direction.z -= 1
        if 's' in self.pressed_keys:
            direction.z += 1
        if 'a' in self.pressed_keys:
            direction.x -= 1
        if 'd' in self.pressed_keys:
            direction.x += 1
        if 'q' in self.pressed_keys:
            direction.y -= 1
        if 'e' in self.pressed_keys:
            direction.y += 1
        
        if direction.length() > 0:
            direction = direction.normalize()
            direction = direction.rotate_y(self.scene_camera.rotation.y)
            self.scene_camera.position = self.scene_camera.position + direction * self.scene_camera_speed
        
        self.camera_info.config(text=f"Camera: ({self.scene_camera.position.x:.1f}, {self.scene_camera.position.y:.1f}, {self.scene_camera.position.z:.1f})")

    def draw_textured_face(self, points_3d, texture, color):
        if len(points_3d) < 3:
            return
            
        points_2d = []
        depths = []
        for point in points_3d:
            point_2d = self.project_3d_to_2d(point)
            if point_2d and point_2d[0] is not None:
                points_2d.append(point_2d)
                depths.append(point.z)
        
        if len(points_2d) < 3:
            return
            
        try:
            xs = [p[0] for p in points_2d]
            ys = [p[1] for p in points_2d]
            min_x, max_x = int(max(0, min(xs))), int(min(799, max(xs)))
            min_y, max_y = int(max(0, min(ys))), int(min(599, max(ys)))
            
            if min_x >= max_x or min_y >= max_y:
                return
                
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    if self.is_point_in_polygon(x, y, points_2d):
                        z = self.interpolate_depth(x, y, points_2d, depths)
                        
                        if self.zbuffer.test_and_set(x, y, z):
                            tex_x = int((x - min_x) / (max_x - min_x + 1) * (texture.width - 1))
                            tex_y = int((y - min_y) / (max_y - min_y + 1) * (texture.height - 1))
                            pixel_color = texture.get_pixel(tex_x, tex_y)
                            
                            self.scene_canvas.create_rectangle(
                                x, y, x+1, y+1, 
                                outline=pixel_color, fill=pixel_color, width=0
                            )
        except Exception:
            return

    def is_point_in_polygon(self, x, y, points):
        n = len(points)
        inside = False
        p1x, p1y = points[0]
        for i in range(n + 1):
            p2x, p2y = points[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def interpolate_depth(self, x, y, points_2d, depths):
        return sum(depths) / len(depths)

    def draw_textured_cube(self, obj, camera_pos, camera_rot):
        vertices = []
        for x in [-0.5, 0.5]:
            for y in [-0.5, 0.5]:
                for z in [-0.5, 0.5]:
                    vertex = Vector3(
                        x * obj.transform.scale.x + obj.transform.position.x,
                        y * obj.transform.scale.y + obj.transform.position.y,
                        z * obj.transform.scale.z + obj.transform.position.z
                    )
                    vertices.append(vertex)
        
        visible_points = 0
        for vertex in vertices:
            point_2d = self.project_3d_to_2d(vertex, camera_pos, camera_rot)
            if point_2d and point_2d[0] is not None:
                visible_points += 1
        
        if visible_points < 4:
            return
        
        faces = [
            [0, 1, 3, 2], [4, 5, 7, 6], [0, 4, 6, 2],
            [1, 5, 7, 3], [0, 1, 5, 4], [2, 3, 7, 6]
        ]
        
        texture = self.texture_manager.textures["cube"]
        
        for face in faces:
            face_vertices = [vertices[i] for i in face]
            self.draw_textured_face(face_vertices, texture, obj.color)

    def project_3d_to_2d(self, position, camera_pos=None, camera_rot=None):
        if camera_pos is None:
            camera_pos = self.scene_camera.position
        if camera_rot is None:
            camera_rot = self.scene_camera.rotation
        
        pos = Vector3(
            position.x - camera_pos.x,
            position.y - camera_pos.y, 
            position.z - camera_pos.z
        )
        
        y_rad = math.radians(camera_rot.y)
        x_rad = math.radians(camera_rot.x)
        
        new_x = pos.x * math.cos(y_rad) + pos.z * math.sin(y_rad)
        new_z = -pos.x * math.sin(y_rad) + pos.z * math.cos(y_rad)
        
        new_y = pos.y * math.cos(x_rad) - new_z * math.sin(x_rad)
        final_z = pos.y * math.sin(x_rad) + new_z * math.cos(x_rad)
        
        if final_z > 0.1:
            factor = 50.0 / final_z
            x = new_x * factor + 400
            y = -new_y * factor + 300
            return (x, y)
        
        return (None, None)

    def draw_scene(self):
        self.scene_canvas.delete("all")
        self.zbuffer.clear()
        
        if self.game_mode and self.player:
            # В режиме игры используем позицию камеры игрока (от первого лица)
            camera_pos = self.player.get_camera_position()
            camera_rot = self.player.get_camera_rotation()
            mode_text = "PLAY MODE - First Person"
        else:
            # В режиме редактора используем сценную камеру
            camera_pos = self.scene_camera.position
            camera_rot = self.scene_camera.rotation
            mode_text = "EDIT MODE"
        
        for obj in self.objects:
            # В режиме игры НЕ пропускаем визуальный объект игрока - он должен отображаться
            if self.game_mode and self.player and obj == self.player.visual_object:
                # Отрисовываем модель игрока
                pass
                
            if self.render_mode == "textured" and obj.shape == "cube":
                self.draw_textured_cube(obj, camera_pos, camera_rot)
            else:
                self.draw_object_simple(obj, camera_pos, camera_rot)
        
        current_file = os.path.basename(self.current_file) if self.current_file else "Untitled"
        info = f"{mode_text} | Scene: {current_file} | Objects: {len(self.objects)} | Render: {self.render_mode}"
        if self.game_mode and self.player:
            info += f" | Pos: ({self.player.transform.position.x:.1f}, {self.player.transform.position.y:.1f}, {self.player.transform.position.z:.1f})"
            
        self.scene_canvas.create_text(10, 10, text=info, anchor='nw', fill='white', font=('Arial', 10))
        
        if self.game_mode:
            controls = "WASD/Arrows: Move, Space: Jump"
            self.scene_canvas.create_text(10, 30, text=controls, anchor='nw', fill='#00FF00', font=('Arial', 9))

    def draw_object_simple(self, obj, camera_pos, camera_rot):
        if obj.shape == "cube":
            self.draw_cube_simple(obj, camera_pos, camera_rot)
        elif obj.shape == "sphere":
            self.draw_sphere_simple(obj, camera_pos, camera_rot)

    def draw_cube_simple(self, obj, camera_pos, camera_rot):
        vertices = []
        for x in [-0.5, 0.5]:
            for y in [-0.5, 0.5]:
                for z in [-0.5, 0.5]:
                    vertex = Vector3(
                        x * obj.transform.scale.x + obj.transform.position.x,
                        y * obj.transform.scale.y + obj.transform.position.y, 
                        z * obj.transform.scale.z + obj.transform.position.z
                    )
                    vertices.append(vertex)
        
        edges = [
            (0,1), (1,3), (3,2), (2,0),
            (4,5), (5,7), (7,6), (6,4),
            (0,4), (1,5), (2,6), (3,7)
        ]
        
        for start, end in edges:
            p1 = self.project_3d_to_2d(vertices[start], camera_pos, camera_rot)
            p2 = self.project_3d_to_2d(vertices[end], camera_pos, camera_rot)
            
            if p1 and p2 and p1[0] is not None and p2[0] is not None:
                try:
                    x1, y1 = float(p1[0]), float(p1[1])
                    x2, y2 = float(p2[0]), float(p2[1])
                    self.scene_canvas.create_line(
                        x1, y1, x2, y2, 
                        fill=obj.color, width=2
                    )
                except (ValueError, TypeError):
                    continue
        
        if obj.selected:
            points_2d = []
            for vertex in vertices:
                point = self.project_3d_to_2d(vertex, camera_pos, camera_rot)
                if point and point[0] is not None:
                    points_2d.append(point)
            
            if len(points_2d) >= 2:
                try:
                    xs = [float(p[0]) for p in points_2d if p[0] is not None]
                    ys = [float(p[1]) for p in points_2d if p[1] is not None]
                    
                    if xs and ys:
                        min_x, max_x = min(xs), max(xs)
                        min_y, max_y = min(ys), max(ys)
                        
                        self.scene_canvas.create_rectangle(
                            min_x-5, min_y-5, max_x+5, max_y+5,
                            outline='#007ACC', width=2, dash=(4,2)
                        )
                except (ValueError, TypeError):
                    pass

    def draw_sphere_simple(self, obj, camera_pos, camera_rot):
        center_2d = self.project_3d_to_2d(obj.transform.position, camera_pos, camera_rot)
        if center_2d and center_2d[0] is not None:
            try:
                radius = 20 * obj.transform.scale.x
                x, y = float(center_2d[0]), float(center_2d[1])
                self.scene_canvas.create_oval(x-radius, y-radius, x+radius, y+radius, 
                                            outline=obj.color, width=2)
            except (ValueError, TypeError):
                pass

    def start_loop(self):
        def update():
            if not self.game_mode:
                self.update_scene_camera()
        
            if self.game_mode and self.player:
                collidable_objects = [obj for obj in self.objects if hasattr(obj, 'collision_enabled') and obj.collision_enabled]
                self.player.update(self.pressed_keys, collidable_objects)
            
                # Обновляем позицию визуального объекта игрока
                if self.player.visual_object:
                    self.player.visual_object.transform.position = self.player.transform.position
                    self.player.visual_object.transform.rotation = self.player.transform.rotation
                
                # Обновляем скрипты каждый кадр
                self.script_interpreter.update_scripts()
        
            self.draw_scene()
            self.window.after(16, update)
    
        update()

    def run(self):
        self.window.mainloop()

    def new_scene(self):
        self.objects = []
        self.object_list.delete(0, tk.END)
        self.player = None
        self.game_mode = False
        self.current_file = None
        self.play_button.config(text="▶ Play", bg='#4CAF50')
        self.window.title("GayEngine - Untitled")
        self.create_default_scene()
        self.log("New scene created!")

if __name__ == "__main__":
    print("Initializing GayEngine with FULL GayScript v2.0 support...")
    print("Features: Multiple Working, Using objects, Collision detection, Line fields")
    engine = GayEngine()
    engine.run()