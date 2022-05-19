import random
from itertools import repeat
from multiprocessing import Pool

from dijkstar import Graph, find_path

from collisionspace import Collisionspace
from configspace_view import ConfigspaceView
from utils import open_greyscale_bmp, GREYSCALE_BLACK


class Configspace:  # shows the way of the robot the algorithm
    def __init__(self, app_page, robot_name: str, collisionspace: Collisionspace):
        robot_bmp = open_greyscale_bmp(robot_name)
        self.__view = ConfigspaceView(app_page, robot_bmp, collisionspace.collision_image)
        self.__min_x = round(robot_bmp.width/2)
        self.__max_x = collisionspace.collision_image.width - round(robot_bmp.width/2)
        self.__min_y = round(robot_bmp.height/2)
        self.__max_y = collisionspace.collision_image.height - round(robot_bmp.height/2)

        self.__init_config_xy = []  # position of the start Image
        self.__goal_config_xy = []  # position of the goal Image

        self.__collision_array_yx = collisionspace.collision_array

        self.edge_graph = Graph()
        self.solution_path_yx = []  # array of Waypoints

    def __add_bidirectional_edge(self, node_index1, node_index2, distance):
        self.edge_graph.add_edge(node_index1, node_index2, distance)
        self.edge_graph.add_edge(node_index2, node_index1, distance)

    def __draw_configuration_state(self):
        self.__view.reset()
        if self.__init_config_xy:
            self.__view.draw_point(self.__init_config_xy[0], self.__init_config_xy[1], 'green')
        if self.__goal_config_xy:
            self.__view.draw_point(self.__goal_config_xy[0], self.__goal_config_xy[1], 'red')

    def __convert_solution_path(self, path, vertex_list_yx):
        start_vertex_yx = vertex_list_yx[0]
        self.solution_path_yx.append(start_vertex_yx)
        self.__view.draw_point(start_vertex_yx[1], start_vertex_yx[0], 'green')
        for vertex_index in path.nodes:
            if vertex_index == 0:
                continue
            next_vertex_yx = vertex_list_yx[vertex_index]
            self.__view.draw_point(next_vertex_yx[1], next_vertex_yx[0], 'purple')
            self.__view.draw_line_yx(start_vertex_yx, next_vertex_yx, 'red')
            self.solution_path_yx.extend(calc_all_points_between_xy(start_vertex_yx, next_vertex_yx))
            start_vertex_yx = next_vertex_yx
        self.__view.draw_point(start_vertex_yx[1], start_vertex_yx[0], 'red')

    def reset(self) -> None:
        self.__init_config_xy = []
        self.__goal_config_xy = []
        self.solution_path_yx = []
        self.edge_graph = Graph()
        self.__view.reset()

    def set_init_config(self, x, y):
        self.__init_config_xy = [x, y]
        self.__draw_configuration_state()

    def set_goal_config(self, x, y):
        self.__goal_config_xy = [x, y]
        self.__draw_configuration_state()

    def execute_SPRM_algorithm(self) -> None:
        self.solution_path_yx = []
        self.edge_graph = Graph()
        distance_r = 90
        point_samples_n = round(self.__collision_array_yx.shape[0] * self.__collision_array_yx.shape[1] / 800)
        # add configuration to vertex structure
        self.edge_graph.add_node(0)
        self.edge_graph.add_node(1)
        vertex_list_yx = [
            (self.__init_config_xy[1], self.__init_config_xy[0]),
            (self.__goal_config_xy[1], self.__goal_config_xy[0])]

        # calculate n free samples
        for i in range(2, point_samples_n + 2):
            while True:
                free_sample_yx = random_point_yx(self.__min_x, self.__max_x, self.__min_y, self.__max_y)
                if self.__collision_array_yx[free_sample_yx[0]][free_sample_yx[1]] > 1:
                    self.edge_graph.add_node(i)
                    vertex_list_yx.append(free_sample_yx)
                    break

        for point_index_tuple in tuples_under_distance(self.__collision_array_yx, vertex_list_yx, distance_r):
            self.__add_bidirectional_edge(point_index_tuple[0],
                                          point_index_tuple[1],
                                          round(calc_distance(
                                              vertex_list_yx[point_index_tuple[0]],
                                              vertex_list_yx[point_index_tuple[1]])))
            self.__view.draw_line_yx(vertex_list_yx[point_index_tuple[0]],
                                     vertex_list_yx[point_index_tuple[1]],
                                     'orange')
        for i in vertex_list_yx:
            self.__view.draw_point(i[1], i[0], 'blue')
        path = find_path(self.edge_graph, 0, 1)
        # draw solution
        self.__convert_solution_path(path, vertex_list_yx)


def random_point_yx(min_width: int, max_width: int, min_height: int, max_height: int) -> []:
    x = random.randrange(min_width, max_width)
    y = random.randrange(min_height, max_height)
    return [y, x]


def calc_distance(point_1yx, point_2yx) -> float:
    return ((point_1yx[0] - point_2yx[0]) ** 2 +
            (point_1yx[1] - point_2yx[1]) ** 2) ** 0.5


def tuples_under_distance(collision_array_yx, points_yx: [], distance) -> []:
    points_neighbour_tuples = []
    for point_index in range(len(points_yx) - 1):
        for next_point_index in range(point_index + 1, len(points_yx)):
            if calc_distance(points_yx[point_index], points_yx[next_point_index]) < distance:
                points_neighbour_tuples.append([point_index, next_point_index])
    with Pool(4) as p:
        valid_edge = p.starmap(
            edge_without_collision,
            zip(repeat(collision_array_yx), repeat(points_yx), points_neighbour_tuples))
    return filter(None, valid_edge)


def edge_without_collision(collision_array_yx, points_yx: [], points_index_tuple: []):
    start_yx = points_yx[points_index_tuple[0]]
    goal_yx = points_yx[points_index_tuple[1]]
    step_range = round(calc_distance(start_yx, goal_yx))
    for step in range(1, step_range):
        point_xy = calc_point_between_xy(start_yx, goal_yx, step, step_range)
        if collision_array_yx[point_xy[1]][point_xy[0]] == GREYSCALE_BLACK:
            return None
    return points_index_tuple


def calc_point_between_xy(start_yx, goal_yx, step, step_range) -> []:
    delta_x = round(step * float(goal_yx[1] - start_yx[1]) / float(step_range))
    delta_y = round(step * float(goal_yx[0] - start_yx[0]) / float(step_range))
    new_x = start_yx[1] + delta_x
    new_y = start_yx[0] + delta_y
    return [new_x, new_y]


def calc_all_points_between_xy(start_yx, goal_yx):
    result = []
    step_range = round(calc_distance(start_yx, goal_yx))
    for step in range(1, step_range):
        result.append(calc_point_between_xy([start_yx[1], start_yx[0]], [goal_yx[1], goal_yx[0]], step, step_range))
    return result
