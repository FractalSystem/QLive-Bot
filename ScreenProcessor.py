from PIL import Image
import pytesseract
import cv2
import time
from multiprocessing.dummy import Pool as ThreadPool

# could use ocr.space online ocr
""" Contains functions to apply computer vision to screenshot of QLive app to extract question and answers using the
 Tesseract OCR. """

pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files (x86)/Tesseract-OCR/tesseract.exe'
SHOW_IMAGES = False
FULL_SCREEN = True


def remove_close_boxes(l):
    accepted_l = [l[0]]
    for i in range(len(l)):
        good = True
        for box in accepted_l:
            if abs(box[0] - l[i][0]) < 30 and abs(box[1] - l[i][1]) < 30:
                good = False
        if good:
            accepted_l.append(l[i])
        else:
            pass
    return accepted_l


def crop_img(img, bounding_box):
    return img[bounding_box[1]:bounding_box[1] + bounding_box[3], bounding_box[0]:bounding_box[0] + bounding_box[2]]


def cv_im_to_string(cv_im):
    return pytesseract.image_to_string(Image.fromarray(cv_im), config="--psm 6 MyConfig")


def cv_im_to_string_singleline(cv_im):
    return pytesseract.image_to_string(Image.fromarray(cv_im), config="--psm 13 MyConfig")


def get_time_left(imgray):
    y = imgray.shape[0]
    x = imgray.shape[1]
    bb = (int(x * 0.3), int(y * 0.2), 500, 500)
    im = crop_img(imgray, bb)
    ret, im = cv2.threshold(im, 240, 255, cv2.THRESH_BINARY)
    im = cv2.bitwise_not(cv2.GaussianBlur(im, (5, 5), 0))
    number = pytesseract.image_to_string(Image.fromarray(im), config='--psm 13 -c tessedit_char_whitelist=0123456789')
    # print(number)
    # cv2.imshow("time left",cv2.bitwise_not(im))
    # cv2.waitKey(0)
    return number


def process_cv_image(im, gray=False):
    """
    Detects white question+answer box using threshold filter and contours, then crops to bb
    Detects answer boxes by applying filter for that grey, then draws contours, finds their bounding boxes,
    filters the boxes by size then proximity to each other. Finally draws bounding box for question based on
    width of answer boxes and relative height of the image based on a ratio

    :open_cv_image im:
    :is_the_image_grayscale gray:
    :return question and answers list:
    """
    start_time = time.time()
    if gray:
        imgray = im
    else:
        imgray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    # Crop image to size
    y = imgray.shape[0]
    x = imgray.shape[1]
    x_to_crop = int(x * 0.035)
    y_to_crop = int(y * 0.5)
    bb = (x_to_crop, y_to_crop, x - 2 * x_to_crop, y)
    imgray = crop_img(imgray, bb)
    ret, masked_im = cv2.threshold(imgray, 250, 255, cv2.THRESH_BINARY)
    im2, contours, hierarchy = cv2.findContours(masked_im, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(masked_im, contours, -1, 150, 3)
    boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        boxes.append([x, y, w, h])
    if len(boxes) == 0:
        raise Exception("Couldn't find contour box")
    boxes.sort(key=lambda elem: elem[2] * elem[3], reverse=True)  # largest boxes first
    size = boxes[0][2] * boxes[0][3]
    # check if the largest box is of the roughly expected size
    if size > 23343 * 0.8 and size < 23343 * 1.2:
        bb = boxes[0]
        question_im = crop_img(imgray, bb)
        # crop imgray to get answers only
        imgray = imgray[bb[1] + bb[3] + 5:imgray.shape[0], 0:imgray.shape[0]]
    else:
        if SHOW_IMAGES:
            cv2.imshow(" ", masked_im)
            cv2.waitKey()
        raise Exception("Couldn't find question box (are bounds wrong?)")

    ret, masked_im = cv2.threshold(imgray, 150, 170, cv2.THRESH_BINARY)  # get answer borders only ideally
    im2, contours, hierarchy = cv2.findContours(masked_im, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        boxes.append([x, y, w, h])
    boxes = list(filter(lambda elem: elem[2] * elem[3] > 25000, boxes))  # remove small boxes
    if len(boxes) < 3:
        raise SyntaxError("Error: couldn't recognise boxes")
    boxes = remove_close_boxes(boxes)
    question = ""
    answers = []
    if len(boxes) > 0:
        a_images = []
        answers = []
        lowest_y = 10000
        q_image = []
        for box in boxes:
            cropped_im = crop_img(imgray, box)
            ret, cropped_im = cv2.threshold(cropped_im, 200, 255, cv2.THRESH_BINARY)
            a_images.append(cropped_im)
            if box[1] < lowest_y:
                lowest_y = box[1]

        cropped_im = imgray[0:lowest_y, 0:imgray.shape[1]]
        q_image.append(cropped_im)
        # multithread tesseract
        if len(q_image) == 1 and len(a_images) >= 2:
            pool = ThreadPool(len(q_image) + len(a_images))
            a_images.extend(q_image)
            results = pool.map(cv_im_to_string, a_images)
            pool.close()
            pool.join()
            question = results[len(a_images) - 1]
            for i in range(len(a_images) - 1):
                answers.append(results[i])
    if SHOW_IMAGES:
        for i in range(len(a_images)):
            cv2.imshow(f"w{i}", a_images[i])

    if SHOW_IMAGES:
        for box in boxes:
            cv2.rectangle(imgray, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), (60, 50, 80))
        cv2.imshow("window", imgray)
        cv2.waitKey()
    answers.reverse()
    print("--- %s seconds ---" % (time.time() - start_time))

    print(question)
    print(answers)
    return (question, answers)


def process_file(filename):
    # used in testing to read file directly.
    return process_cv_image(cv2.imread(filename))
