import requests
import base64
import json


def image_to_tags(filepath):
    """ Interacts with the Google Vision API to automatically tag images. Useful for identifying celebrities etc."""
    ak = "[API key here]"
    searchUrl = 'https://vision.googleapis.com/v1/images:annotate?key=%s' % ak
    with open(filepath, 'rb') as imgFile:
        image = base64.b64encode(imgFile.read())
    body = """{
      "requests": [
        {
          "image": {
            "content": "%s"
          },
          "features": [
            {
              "type": "LOGO_DETECTION"
            },
            {
              "type": "WEB_DETECTION"
            }
          ]
        }
      ]
    }""" % image.decode("utf-8")
    response = requests.post(searchUrl, data=body, verify=False)
    logo_str = ""
    web_string = ""
    best_guess_str = ""
    # print(response.content.decode())
    if response.status_code == 200:
        try:
            obj = json.loads(response.content.decode()).get("responses")[0]
            logos = obj.get("logoAnnotations")
            webDetection = obj.get("webDetection")
            if logos is not None:
                logo_str = "Logos: " + ", ".join(str(logo.get("description")) for logo in logos)
            if webDetection is not None:
                web_string = "Web entities: " + ", ".join(
                    str(entity.get("description")) for entity in webDetection.get("webEntities"))
                best_guess_str = "Best guess: " + ", ".join(
                    str(label.get("label")) for label in webDetection.get("bestGuessLabels"))

        except Exception as e:
            print("Vision api: Parsing response failed for the following reason")
            print(e)
    else:
        raise Exception("Vision API did not return code 200")
    return best_guess_str + "\n" + web_string +"\n"+ logo_str
    # print(image.decode("utf-8"))

if __name__ == "__main__":
    image_to_tags("Tata_logo.png")