import pandas as pd
import plotly.graph_objects as go
import datetime
import os
import warnings
import sys
import numpy as np
import rasterio
from PIL import Image
import io
import base64
import argparse

# 忽略警告
warnings.filterwarnings("ignore")

# 数据路径
data_path = r"F:\Data\weibo.xls"
background_path = r"F:\Data\result\beijin.tif"
output_html_path = r"weibo_visualization.html"

class WeiboHTMLVisualization:
    def __init__(self, data_path=data_path, background_path=background_path, output_html_path=output_html_path, 
                 band_r=1, band_g=2, band_b=3, contrast=1.2, brightness=1.1, no_enhance=False):
        # 保存路径和参数
        self.data_path = data_path
        self.background_path = background_path
        self.output_html_path = output_html_path
        self.band_r = band_r
        self.band_g = band_g
        self.band_b = band_b
        self.contrast = contrast
        self.brightness = brightness
        self.no_enhance = no_enhance
        
        # 读取数据
        self.df = pd.read_excel(self.data_path)
        self.df['TIME'] = pd.to_datetime(self.df['TIME'])
            
        # 加载背景图
        self.background_loaded = False
        self.background_img = None
        self.background_extent = None
        
        if os.path.exists(self.background_path):
            self.src = rasterio.open(self.background_path)
            self.background_loaded = True
            
            # 获取背景图的边界
            self.background_extent = [
                self.src.bounds.left, 
                self.src.bounds.right,
                self.src.bounds.bottom, 
                self.src.bounds.top
            ]
            
        # 初始化点集
        self.points_7_8 = None
        self.points_8_9 = None
        self.points_9_10 = None
        
        # 处理数据
        self.process_data()
            
    def process_data(self):
        """处理数据，按时间段分组"""
        # 创建时间过滤条件
        time_7 = datetime.time(7, 0, 0)
        time_8 = datetime.time(8, 0, 0)
        time_9 = datetime.time(9, 0, 0)
        time_10 = datetime.time(10, 0, 0)
        
        # 过滤7-8点的数据
        mask_7_8 = (self.df['TIME'].dt.time >= time_7) & (self.df['TIME'].dt.time < time_8)
        self.points_7_8 = self.df[mask_7_8]
        
        # 过滤8-9点的数据
        mask_8_9 = (self.df['TIME'].dt.time >= time_8) & (self.df['TIME'].dt.time < time_9)
        self.points_8_9 = self.df[mask_8_9]
        
        # 过滤9-10点的数据
        mask_9_10 = (self.df['TIME'].dt.time >= time_9) & (self.df['TIME'].dt.time < time_10)
        self.points_9_10 = self.df[mask_9_10]
    
    def prepare_background_image(self):
        """准备背景图像，转换为适合Plotly的格式"""
        if not self.background_loaded or self.src is None:
            return None
            
        try:
            # 使用rasterio直接读取并处理图像数据
            if self.src.count >= 3:  # 如果有3个或更多波段（RGB）
                # 读取前三个波段作为RGB
                rgb_bands = np.zeros((self.src.height, self.src.width, 3), dtype=np.uint8)
                
                # 使用指定的波段组合
                selected_bands = (self.band_r, self.band_g, self.band_b)
                
                # 检查波段是否有效
                if any(b > self.src.count for b in selected_bands):
                    selected_bands = (1, 2, 3)
                
                # 读取所选波段
                for i in range(3):
                    band_idx = selected_bands[i]
                    if band_idx <= self.src.count:
                        band_data = self.src.read(band_idx)
                        # 归一化到0-255
                        min_val = np.percentile(band_data, 2)
                        max_val = np.percentile(band_data, 98)
                        if max_val > min_val:
                            normalized = np.clip((band_data - min_val) / (max_val - min_val) * 255, 0, 255).astype(np.uint8)
                        else:
                            normalized = np.zeros_like(band_data, dtype=np.uint8)
                        rgb_bands[:, :, i] = normalized
                
                # 创建PIL图像
                image = Image.fromarray(rgb_bands)
                
                # 图像增强
                if not self.no_enhance:
                    from PIL import ImageEnhance
                    # 增强对比度
                    enhancer = ImageEnhance.Contrast(image)
                    image = enhancer.enhance(self.contrast)
                    
                    # 增强亮度
                    enhancer = ImageEnhance.Brightness(image)
                    image = enhancer.enhance(self.brightness)
            
            else:  # 如果只有一个波段（灰度）
                band = self.src.read(1)
                # 归一化处理
                min_val = np.percentile(band, 2)
                max_val = np.percentile(band, 98)
                if max_val > min_val:
                    band_norm = np.clip((band - min_val) / (max_val - min_val) * 255, 0, 255).astype(np.uint8)
                else:
                    band_norm = np.zeros_like(band, dtype=np.uint8)
                
                # 转换为RGB格式
                rgb_bands = np.dstack([band_norm, band_norm, band_norm])
                image = Image.fromarray(rgb_bands)
            
            # 保存图像到内存
            buf = io.BytesIO()
            image.save(buf, format='PNG')
            buf.seek(0)
            
            # 转换为base64编码
            img_str = base64.b64encode(buf.read()).decode('utf-8')
            
            return f"data:image/png;base64,{img_str}"
        except Exception:
            return None
            
    def create_html_visualization(self):
        """创建HTML可视化"""
        # 获取数据的边界
        x_min, x_max = self.df['POINT_X'].min(), self.df['POINT_X'].max()
        y_min, y_max = self.df['POINT_Y'].min(), self.df['POINT_Y'].max()
        
        # 添加一些边距
        x_padding = (x_max - x_min) * 0.05
        y_padding = (y_max - y_min) * 0.05
        
        # 准备背景图像
        background_img_src = self.prepare_background_image()
        
        # 创建图表
        fig = go.Figure()
        
        # 添加背景图（如果有）
        if background_img_src:
            fig.update_layout(
                images=[dict(
                    source=background_img_src,
                    xref="x",
                    yref="y",
                    x=self.background_extent[0],
                    y=self.background_extent[3],
                    sizex=self.background_extent[1] - self.background_extent[0],
                    sizey=self.background_extent[3] - self.background_extent[2],
                    sizing="stretch",
                    opacity=1.0,
                    layer="below"
                )]
            )
        
        # 设置布局
        fig.update_layout(
            title="微博数据可视化 - 按时间段显示",
            title_font_size=20,
            autosize=True,
            height=800,
            width=1200,
            hovermode="closest",
            xaxis=dict(
                range=[x_min - x_padding, x_max + x_padding],
                title="经度"
            ),
            yaxis=dict(
                range=[y_min - y_padding, y_max + y_padding],
                title="纬度"
            ),
            updatemenus=[
                dict(
                    type="buttons",
                    direction="right",
                    x=0.1,
                    y=0,
                    buttons=[
                        dict(
                            label="7点-8点",
                            method="update",
                            args=[{"visible": [True, False, False]},
                                  {"title": "微博数据可视化 - 7点-8点"}]
                        ),
                        dict(
                            label="8点-9点",
                            method="update",
                            args=[{"visible": [True, True, False]},
                                  {"title": "微博数据可视化 - 7点-9点"}]
                        ),
                        dict(
                            label="9点-10点",
                            method="update",
                            args=[{"visible": [True, True, True]},
                                  {"title": "微博数据可视化 - 7点-10点"}]
                        ),
                        dict(
                            label="重置",
                            method="update",
                            args=[{"visible": [False, False, False]},
                                  {"title": "微博数据可视化 - 按时间段显示"}]
                        )
                    ]
                )
            ]
        )
        
        # 添加7-8点的数据
        if len(self.points_7_8) > 0:
            # 为每个点创建时间字符串
            time_texts = self.points_7_8['TIME'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            fig.add_trace(
                go.Scattergl(
                    x=self.points_7_8['POINT_X'],
                    y=self.points_7_8['POINT_Y'],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color='red',
                        opacity=0.9,
                        line=dict(width=1.5, color='white')
                    ),
                    name='7点-8点',
                    visible=False,
                    text=time_texts,
                    hovertemplate='经度: %{x}<br>纬度: %{y}<br>时间: %{text}'
                )
            )
        
        # 添加8-9点的数据
        if len(self.points_8_9) > 0:
            # 为每个点创建时间字符串
            time_texts = self.points_8_9['TIME'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            fig.add_trace(
                go.Scattergl(
                    x=self.points_8_9['POINT_X'],
                    y=self.points_8_9['POINT_Y'],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color='blue',
                        opacity=0.9,
                        line=dict(width=1.5, color='white')
                    ),
                    name='8点-9点',
                    visible=False,
                    text=time_texts,
                    hovertemplate='经度: %{x}<br>纬度: %{y}<br>时间: %{text}'
                )
            )
        
        # 添加9-10点的数据
        if len(self.points_9_10) > 0:
            # 为每个点创建时间字符串
            time_texts = self.points_9_10['TIME'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            fig.add_trace(
                go.Scattergl(
                    x=self.points_9_10['POINT_X'],
                    y=self.points_9_10['POINT_Y'],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color='green',
                        opacity=0.9,
                        line=dict(width=1.5, color='white')
                    ),
                    name='9点-10点',
                    visible=False,
                    text=time_texts,
                    hovertemplate='经度: %{x}<br>纬度: %{y}<br>时间: %{text}'
                )
            )
        
        # 保存为HTML文件
        config = {
            'scrollZoom': True,
            'displayModeBar': True,
            'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect', 'eraseshape']
        }
        fig.write_html(self.output_html_path, auto_open=False, config=config)
        return True

if __name__ == "__main__":
    # 允许从命令行参数传入路径
    parser = argparse.ArgumentParser(description='微博数据可视化')
    parser.add_argument('--data', type=str, default=data_path, help='微博数据文件路径')
    parser.add_argument('--background', type=str, default=background_path, help='背景图文件路径')
    parser.add_argument('--output', type=str, default=output_html_path, help='输出HTML文件路径')
    parser.add_argument('--band-r', type=int, default=1, help='红色通道使用的波段')
    parser.add_argument('--band-g', type=int, default=2, help='绿色通道使用的波段')
    parser.add_argument('--band-b', type=int, default=3, help='蓝色通道使用的波段')
    parser.add_argument('--contrast', type=float, default=1.2, help='对比度增强因子(默认1.2)')
    parser.add_argument('--brightness', type=float, default=1.1, help='亮度增强因子(默认1.1)')
    parser.add_argument('--no-enhance', action='store_true', help='不进行图像增强')
    args = parser.parse_args()
    
    # 创建可视化实例
    viz = WeiboHTMLVisualization(
        data_path=args.data,
        background_path=args.background,
        output_html_path=args.output,
        band_r=args.band_r,
        band_g=args.band_g,
        band_b=args.band_b,
        contrast=args.contrast,
        brightness=args.brightness,
        no_enhance=args.no_enhance
    )
    
    # 创建HTML可视化
    viz.create_html_visualization()
    print(f"HTML可视化已生成，文件路径: {viz.output_html_path}") 