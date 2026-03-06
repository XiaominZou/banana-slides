"""
千帆PaddleOCR-VL Provider
基于千帆AI应用开发中心的PaddleOCR-VL模型，提供强大的文档解析和文字识别能力

API文档: https://cloud.baidu.com/doc/qianfan-api/s/zmho8omz3
"""

import logging
import base64
import requests
from typing import Dict, List, Any, Optional
from PIL import Image
import io

logger = logging.getLogger(__name__)


class QianfanOCRProvider:
    """千帆PaddleOCR-VL Provider

    特点：
    - 版面分析：自动识别标题、段落等
    - 图表识别：柱状图、饼图转表格
    - 方向矫正：0°、90°、180°、270°旋转
    - 扭曲矫正：处理褶皱和倾斜
    """

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://qianfan.baidubce.com/v2/ocr/paddleocr",
    ):
        self.api_key = api_key
        self.api_base = api_base
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _encode_image(self, image: Image.Image) -> str:
        """将PIL Image转换为Base64字符串"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str

    def recognize(
        self,
        image: Image.Image,
        use_layout_detection: bool = True,
        use_chart_recognition: bool = True,
        use_doc_unwarping: bool = False,
        use_doc_orientation_classify: bool = False,
        visualize: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """识别图片中的文字和版面信息

        Args:
            image: PIL Image对象
            use_layout_detection: 是否使用版面分析（推荐）
            use_chart_recognition: 是否识别图表
            use_doc_unwarping: 是否进行扭曲矫正
            use_doc_orientation_classify: 是否进行方向矫正
            visualize: 是否返回可视化图像
            **kwargs: 其他参数

        Returns:
            Dict: 包含识别结果的字典
        """
        try:
            image_base64 = self._encode_image(image)

            payload = {
                "model": "paddleocr-vl-0.9b",
                "file": image_base64,
                "fileType": 1,  # 1表示图像文件
                "useLayoutDetection": use_layout_detection,
                "useChartRecognition": use_chart_recognition,
                "useDocUnwarping": use_doc_unwarping,
                "useDocOrientationClassify": use_doc_orientation_classify,
                "visualize": visualize,
            }

            # 可选参数
            if "layoutNms" in kwargs:
                payload["layoutNms"] = kwargs["layoutNms"]
            if "repetitionPenalty" in kwargs:
                payload["repetitionPenalty"] = kwargs["repetitionPenalty"]
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            if "topP" in kwargs:
                payload["topP"] = kwargs["topP"]
            if "minPixels" in kwargs:
                payload["minPixels"] = kwargs["minPixels"]
            if "maxPixels" in kwargs:
                payload["maxPixels"] = kwargs["maxPixels"]

            response = requests.post(
                self.api_base, headers=self.headers, json=payload, timeout=30
            )

            if response.status_code != 200:
                logger.error(
                    f"千帆OCR调用失败: {response.status_code}, {response.text}"
                )
                return {
                    "success": False,
                    "error": f"API调用失败: {response.status_code}",
                    "text_items": [],
                }

            result = response.json()

            if "error" in result:
                logger.error(f"千帆OCR返回错误: {result['error']}")
                return {"success": False, "error": result["error"], "text_items": []}

            return self._parse_result(result)

        except Exception as e:
            logger.error(f"千帆OCR识别异常: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e), "text_items": []}

    def _parse_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """解析千帆OCR返回的结果

        Args:
            result: 千帆OCR原始返回结果

        Returns:
            Dict: 标准化后的识别结果
        """
        try:
            text_items = []

            if "result" in result and "layoutParsingResults" in result["result"]:
                layout_results = result["result"]["layoutParsingResults"]

                for page_result in layout_results:
                    if "prunedResult" in page_result:
                        parsing_list = page_result["prunedResult"].get(
                            "parsing_res_list", []
                        )

                        for item in parsing_list:
                            text_item = {
                                "text": item.get("block_content", ""),
                                "bbox": item.get("block_bbox", []),
                                "label": item.get("block_label", "text"),
                                "id": item.get("block_id", 0),
                            }
                            text_items.append(text_item)

            return {"success": True, "text_items": text_items, "raw_result": result}

        except Exception as e:
            logger.error(f"解析千帆OCR结果失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"结果解析失败: {str(e)}",
                "text_items": [],
            }

    def recognize_text_only(self, image: Image.Image) -> Dict[str, Any]:
        """仅识别文字（不进行版面分析）

        Args:
            image: PIL Image对象

        Returns:
            Dict: 包含文字识别结果的字典
        """
        return self.recognize(
            image, use_layout_detection=False, use_chart_recognition=False
        )

    def recognize_with_layout(self, image: Image.Image) -> Dict[str, Any]:
        """识别文字和版面信息（推荐）

        Args:
            image: PIL Image对象

        Returns:
            Dict: 包含文字和版面信息的字典
        """
        return self.recognize(
            image, use_layout_detection=True, use_chart_recognition=True
        )


def create_qianfan_ocr_provider(
    api_key: str, api_base: str = None
) -> QianfanOCRProvider:
    """创建千帆OCR Provider实例

    Args:
        api_key: 千帆API Key
        api_base: API基础URL（可选）

    Returns:
        QianfanOCRProvider: 千帆OCR Provider实例
    """
    if api_base is None:
        api_base = "https://qianfan.baidubce.com/v2/ocr/paddleocr"

    return QianfanOCRProvider(api_key=api_key, api_base=api_base)
