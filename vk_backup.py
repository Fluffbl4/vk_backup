import os
import sys
import requests
import json
import tqdm
from vk_api import VkApi


class PhotoDownloader:
    def __init__(self, vk_token, ya_disk_token, user_id=None, count=5):
        self.vk_token = vk_token
        self.ya_disk_token = ya_disk_token
        self.user_id = user_id
        self.count = count
        self.session = None
        self.progress_bar = None

    def auth_vk(self):
        try:
            self.session = VkApi(token=self.vk_token).get_api()
        except Exception as e:
            print(f"Произошла ошибка при авторизации ВКонтакте: {e}")
            sys.exit(1)

    def check_folder_exists_on_ya_disk(self, folder_name):
        url = "https://cloud-api.yandex.net/v1/disk/resources"
        headers = {"Authorization": f"OAuth {self.ya_disk_token}"}
        params = {"path": folder_name}
        response = requests.get(url, headers=headers, params=params)
        return response.ok

    def create_folder_on_ya_disk(self, folder_name):
        url = "https://cloud-api.yandex.net/v1/disk/resources"
        headers = {"Authorization": f"OAuth {self.ya_disk_token}"}
        params = {"path": folder_name}
        response = requests.put(url, headers=headers, params=params)
        if not response.ok:
            print(f"Не удалось создать папку на Яндекс.Диске: {response.text}")
            sys.exit(1)

    def get_existing_files_in_folder(self, folder_name):
        url = "https://cloud-api.yandex.net/v1/disk/resources"
        headers = {"Authorization": f"OAuth {self.ya_disk_token}"}
        params = {"path": folder_name}
        response = requests.get(url, headers=headers, params=params)
        if response.ok:
            existing_files = [
                item["name"] for item in response.json()["_embedded"]["items"]
            ]
            return existing_files
        else:
            print(f"Не удалось получить список файлов в папке: {response.text}")
            return []

    def get_max_size_photos(self):
        try:
            photos = self.session.photos.get(
                owner_id=self.user_id, album_id="profile", extended=1
            )["items"]
        except Exception as e:
            print(f"Произошла ошибка при получении фотографий: {e}")
            sys.exit(1)

        max_size_photos = []
        for photo in photos:
            sizes = sorted(
                photo["sizes"], key=lambda x: x["width"] * x["height"], reverse=True
            )
            max_size_photo = sizes[0]
            max_size_photos.append(
                {
                    "url": max_size_photo["url"],
                    "likes_count": photo["likes"]["count"],
                    "id": photo["id"],
                }
            )

        return max_size_photos[: self.count]

    def download_and_upload_to_ya_disk(self, folder_name):
        if not self.check_folder_exists_on_ya_disk(folder_name):
            self.create_folder_on_ya_disk(folder_name)

        existing_files = self.get_existing_files_in_folder(folder_name)
        max_size_photos = self.get_max_size_photos()

        results = []
        self.progress_bar = tqdm.tqdm(total=len(max_size_photos), desc="Загрузка")
        for photo in max_size_photos:
            filename = f"{folder_name}/{photo['likes_count']}.jpg"
            if f"{photo['likes_count']}.jpg" not in existing_files:
                response = requests.get(photo["url"])
                if response.status_code == 200:
                    file_data = response.content
                    success = self.upload_to_ya_disk(file_data, filename)

                    if success:
                        results.append(
                            {
                                "filename": filename,
                                "likes_count": photo["likes_count"],
                                "photo_id": photo["id"],
                            }
                        )
                        print(f"Фото успешно сохранено: {filename}")
                    else:
                        print(f"Не удалось сохранить фото: {filename}")
                else:
                    print(f"Не удалось скачать фото: {photo['url']}")
            else:
                print(f"Фото {filename} уже существует в папке.")

            self.progress_bar.update(1)

        return results

    def upload_to_ya_disk(self, file_data, filename):
        url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
        headers = {"Authorization": f"OAuth {self.ya_disk_token}"}
        params = {"path": filename, "overwrite": True}
        response = requests.post(url, headers=headers, params=params)
        if response.status_code == 200 or response.status_code == 201:
            upload_url = response.json()["href"]
            put_response = requests.put(upload_url, data=file_data)
            return put_response.status_code == 201
        else:
            print(f"Ошибка при получении URL для загрузки файла: {response.text}")
            return False

    def save_results_to_json(self, results, output_file="photos_info.json"):
        with open(output_file, "w") as outfile:
            json.dump(results, outfile, indent=4)


if __name__ == "__main__":
    VK_TOKEN = input("Введите ваш токен ВКонтакте: ")
    YA_DISK_TOKEN = input("Введите ваш токен Яндекс.Диска: ")
    USER_ID = input("Введите ID пользователя: ")
    COUNT = int(input("Укажите количество фотографий для загрузки (по умолчанию 5): ") or 5)

    downloader = PhotoDownloader(VK_TOKEN, YA_DISK_TOKEN, USER_ID, COUNT)
    downloader.auth_vk()
    folder_name = f"photos_{USER_ID}"
    results = downloader.download_and_upload_to_ya_disk(folder_name)
    downloader.save_results_to_json(results)

    print("\nПрограмма завершена.")