import torch
import cv2
import os
import shutil
from google.colab.patches import cv2_imshow
import numpy as np

"""## Reading Images"""

i = cv2.imread("/content/image-002.jpg")
i = cv2.resize(i,(309,129))
cv2.imwrite("/content/image-002.jpg", i)
print(i.shape)

j = cv2.imread("/content/image-003.jpg")
print(j.shape)

cv2_imshow(i)

cv2_imshow(j)

"""## Generating Depth Map"""

min_disp = 0
max_disp = 32
num_disp = max_disp - min_disp
uniquenessRatio = 10
speckleWindowSize = 100
speckleRange = 32
disp12MaxDiff = 0
block_size = 9
sp = cv2.StereoSGBM_create(
    minDisparity=min_disp,
    numDisparities=num_disp,
    blockSize=block_size,
    uniquenessRatio=uniquenessRatio,
    speckleWindowSize=speckleWindowSize,
    speckleRange=speckleRange,
    disp12MaxDiff=disp12MaxDiff,
    P1=600,
    P2=2400)
disparity = sp.compute(i,j)

ndisp = cv2.normalize(disparity,None,0,255,cv2.NORM_MINMAX,cv2.CV_8U)
cv2_imshow(ndisp)

"""## Getting V-Disparity Map"""

import numpy as np
v_disparity_image = np.zeros((ndisp.shape[0], ndisp.max()+1))

for y in range(v_disparity_image.shape[0]):
  for x in range(v_disparity_image.shape[1]):
    if ndisp[y,x] > 0:
      v_disparity_image[y, ndisp[y,x]] += 1

cv2_imshow(v_disparity_image)

# v_disparity_image = (v_disparity_image*255).astype(np.uint8)
v_disparity_image = v_disparity_image.astype(np.uint8)

cv2_imshow(v_disparity_image)

np.unique(v_disparity_image)

threshold_value = 15
_, binary_v_disparity = cv2.threshold(v_disparity_image, threshold_value, 255, cv2.THRESH_BINARY)
cv2_imshow(binary_v_disparity)

"""## Applying Hough Transforms"""

import numpy as np
import matplotlib.pyplot as plt
import cv2

def hough_line_transform(image, theta_res=1, rho_res=1):
    # Get image dimensions
    height, width = image.shape

    # Define the maximum possible distance from the origin to a point in the image
    max_rho = int(np.sqrt(height ** 2 + width ** 2))

    # Create the accumulator matrix
    accumulator = np.zeros((2 * max_rho, int(180 / theta_res)), dtype=np.uint64)

    # Create arrays for theta and rho values
    theta_values = np.deg2rad(np.arange(-90, 90, theta_res))
    rho_values = np.arange(-max_rho, max_rho, rho_res)

    # Find non-zero pixels (edges) in the binary image
    edge_points = np.argwhere(image > 0)

    # Perform the Hough Transform
    for edge_point in edge_points:
        y, x = edge_point
        for theta_idx, theta in enumerate(theta_values):
            rho = int(x * np.cos(theta) + y * np.sin(theta))
            rho_idx = int(rho + max_rho)
            accumulator[rho_idx, theta_idx] += 1

    return accumulator, theta_values, rho_values

def plot_hough_lines(image, accumulator, theta_values, rho_values, threshold):
    # Find indices of accumulator values above the threshold
    rho_indices, theta_indices = np.where(accumulator > threshold)
    global line_points
    line_points = []

    # Plot the original image
    plt.imshow(image, cmap='gray')

    # Plot the detected lines
    for i in range(len(rho_indices)):
        rho = rho_values[rho_indices[i]]
        theta = theta_values[theta_indices[i]]
        a = np.cos(theta)
        b = np.sin(theta)
        x0 = a * rho
        y0 = b * rho
        x1 = int(x0 + 1000 * (-b))
        y1 = int(y0 + 1000 * (a))
        x2 = int(x0 - 1000 * (-b))
        y2 = int(y0 - 1000 * (a))
        plt.plot([x1, x2], [y1, y2], 'r')
        line_points.append([(x1,y1),(x2,y2)])

    plt.xlim(0, image.shape[1])
    plt.ylim(image.shape[0], 0)
    plt.show()

if __name__ == "__main__":
    # Load an example image (replace with your image path)
    # image = cv2.imread('image.jpg', cv2.IMREAD_GRAYSCALE)
    image = v_disparity_image

    # Apply edge detection (you can use a different method if needed)
    edges = cv2.Canny(image, 50, 150)

    # Perform the Hough Line Transform
    accumulator, theta_values, rho_values = hough_line_transform(edges, theta_res=1, rho_res=1)

    # Set a threshold for line detection (adjust as needed)
    threshold = 33

    # Plot the image with detected lines
    plot_hough_lines(image, accumulator, theta_values, rho_values, threshold)

line_points

"""## Finding the intersection point of the lines detected by the Hough Transform"""

def find_intersection(line1, line2):
    (x1, y1), (x2, y2) = line1[0], line1[1]
    (x3, y3), (x4, y4) = line2[0], line2[1]

    # Calculate the slopes of the lines
    m1 = (y2 - y1) / (x2 - x1) if x2 - x1 != 0 else float('inf')
    m2 = (y4 - y3) / (x4 - x3) if x4 - x3 != 0 else float('inf')

    # Check if the lines are parallel
    if m1 == m2:
        return None

    # Calculate the intersection point
    if m1 == float('inf'):
        x = x1
        y = m2 * (x - x3) + y3
    elif m2 == float('inf'):
        x = x3
        y = m1 * (x - x1) + y1
    else:
        x = (y3 - y1 + m1 * x1 - m2 * x3) / (m1 - m2)
        y = m1 * (x - x1) + y1

    # Check if the intersection point is within the line segments
    if (
        min(x1, x2) <= x <= max(x1, x2) and
        min(y1, y2) <= y <= max(y1, y2) and
        min(x3, x4) <= x <= max(x3, x4) and
        min(y3, y4) <= y <= max(y3, y4)
    ):
        return (x, y)
    else:
        return None

def find_all_intersections(line_segments):
    intersections = []
    for i in range(len(line_segments)):
        for j in range(i + 1, len(line_segments)):
            intersection = find_intersection(line_segments[i], line_segments[j])
            if intersection is not None:
                intersections.append(intersection)
    return intersections

intersections = find_all_intersections(line_points)
print("Intersection Points:", intersections)

"""## Using the intersection points as a point of reference for the vanishing line"""

t = i.copy()
# t = cv2.circle(t,(int(683.5356112661522), int(-663.9646349757274)),5,(0,0,255),-1)
plt.imshow(t,cmap="gray")
plt.plot([33.25430738419852-40,33.25430738419852+500],[65.23685520042125, 65.23685520042125],'g')
# plt.plot([65,-3],[998,-1000])
plt.xlim(0, t.shape[1])
plt.ylim(t.shape[0], 0)
plt.show()

def line_intersection(line1_start, line1_end, line2_start, line2_end):
    x1, y1 = line1_start
    x2, y2 = line1_end
    x3, y3 = line2_start
    x4, y4 = line2_end

    # Calculate the determinants
    det = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)

    # Check if the lines are parallel (determinant is close to zero)
    if abs(det) < 1e-10:
        return None

    # Calculate the intersection point
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / det
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / det

    return (px, py)

slopes = {}

for idx,line in enumerate(line_points):
  x1 = line[0][0]
  y1 = line[0][1]
  x2 = line[1][0]
  y2 = line[1][1]
  m = (y2 - y1) / (x2 - x1) if x2 - x1 != 0 else float('inf')

  slopes[f"line{idx+1}"] = ([line,abs(m)])

min = float('inf')
min_line = ""

for line in slopes.keys():
  m = slopes[line][1]
  if m < min:
    min = m
    min_line = line

min_height = float('inf')
vanishing_inter = (0,0)
for line in slopes.keys():
  if line == min_line:
    continue
  inter = line_intersection(slopes[min_line][0][0],slopes[min_line][0][1],slopes[line][0][0],slopes[line][0][1])
  print(inter)
  if i.shape[0] - inter[0] < min_height:
    min_height = i.shape[0] - inter[0]
    vanishing_inter = inter

print(vanishing_inter)

t = i.copy()
plt.imshow(t,cmap="gray")
plt.plot([0,t.shape[1]],[vanishing_inter[1], vanishing_inter[1]],'r')
plt.xlim(0, t.shape[1])
plt.ylim(t.shape[0], 0)
plt.show()

g = t[70:130,90:250]
cv2_imshow(g)

"""## Using vanishing line to get the region of interest"""

# Create a mask
mask = np.zeros_like(t)
roi_corners = np.array([[(0, t.shape[0]), (0, vanishing_inter[1]), (t.shape[1], vanishing_inter[1]), (t.shape[1], t.shape[0])]], dtype=np.int32)
cv2.fillPoly(mask, roi_corners, (255, 255, 255))
result = cv2.bitwise_and(t, mask)

cv2_imshow(result)

roi_corners

t.shape

"""## Applying Perspective Transform to get bird's view"""

t[100:130,200:260]
t[70:130,90:250]
height, width = i.shape[0],i.shape[1]
input_pts = np.float32([[90,70],[250,70],[250,130],[90,130]])
output_pts = np.float32([[0,0], [width,0], [width,height],[0,height]])

matrix = cv2.getPerspectiveTransform(input_pts,output_pts)

output = cv2.warpPerspective(t, matrix, (width, height))
cv2_imshow(output)

"""## Blurring and applying threshold to get the edges"""

g = cv2.cvtColor(output, cv2.COLOR_BGR2GRAY)
fine = cv2.bilateralFilter(g, 5, 75, 75)
cv2_imshow(fine)
thresh = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 7, 10)
cv2_imshow(thresh)

f = thresh.copy()

cv2_imshow(f)

f.shape

f

"""## Creating sliding window"""

# x_pts = [x for x in range(0,60,10)]
# y_pts = [x for x in range(100,220,20)]

y_pts = [x for x in range(0,120,20)]
x_pts = [x for x in range(150,280,20)]

y_approx = []


for x,y in zip(x_pts,y_pts):
  r = cv2.rectangle(thresh,(x,y),(x+70,y+20),(255,0,0),2)
  y_approx.append(int((y+y+20)/2))

cv2_imshow(thresh)

"""## Creating pixel distribution of each sliding window"""

max_peak = []
Iwindow = np.zeros(f.shape)
for x in range(-20,120,20):
  for y in range(130,280,20):
    sum_t = sum(f[x,y-20:y])
    if y <= sum_t:
      Iwindow[x,y] = 255
    else:
      Iwindow[x,y] = 0
  cv2_imshow(Iwindow)
  max_peak.append(np.argmax(np.sum(Iwindow, axis=0)))
  Iwindow = np.zeros(f.shape)

max_peak

y_approx

"""## Approximating max_peak and y_approx as points of the detected line or bicycle lane"""

def create_lines_from_points(points, lines = []):
    if len(points) == 0:
        # no more points, return collected lines
        return lines
    else:
        if len(lines) == 0:
            if len(points) == 1:
                raise ValueError('Cannot create line from one point')
            # starting situation, return create_lines_from_points with args:
            # 1: remaining points after first two points
            # 2: line created from first two points
            return create_lines_from_points(points[2:], [(points[0], points[1])])
        else:
            # mid-list situation, return create_lines_from_points with args:
            # 1: remaining points
            # 2: collected lines plus a new line based on one point from
            #    the last line and a point from the list
            return create_lines_from_points(points[1:], lines + [(lines[-1][1], points[0])])

points = [(x,y) for x,y in zip(max_peak[3:],y_approx[3:])]
points

b = np.array(create_lines_from_points(points),np.int32)

b = np.array([[[160,  70],
        [190,  90]],

       [[190,  90],
        [200, 110]]], dtype=np.int32)

b = b.reshape((-1, 1, 2))
b.shape

image = cv2.polylines(i.copy(), [b],
                      False, (0,255,0), 3)

cv2_imshow(image)

